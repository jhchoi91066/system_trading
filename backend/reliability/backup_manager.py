"""
Backup & Disaster Recovery Manager
자동 백업, 증분 백업, 재해 복구 시스템
"""

import os
import json
import gzip
import shutil
import hashlib
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import aiofiles
import sqlite3

logger = logging.getLogger(__name__)

class BackupType(Enum):
    """백업 타입"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"

class BackupStatus(Enum):
    """백업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class BackupMetadata:
    """백업 메타데이터"""
    backup_id: str
    timestamp: str
    backup_type: BackupType
    status: BackupStatus
    file_path: str
    file_size: int = 0
    checksum: str = ""
    compression: bool = True
    duration_seconds: float = 0.0
    error_message: str = ""
    
    def to_dict(self) -> dict:
        data = asdict(self)
        # Enum 값들을 문자열로 변환
        data['backup_type'] = self.backup_type.value
        data['status'] = self.status.value
        return data

class DataSource:
    """백업 데이터 소스"""
    
    def __init__(self, name: str, source_type: str):
        self.name = name
        self.source_type = source_type  # 'json', 'sqlite', 'postgresql', 'files'
    
    async def collect_data(self) -> Any:
        """데이터 수집 - 하위 클래스에서 구현"""
        raise NotImplementedError
    
    async def restore_data(self, data: Any) -> bool:
        """데이터 복원 - 하위 클래스에서 구현"""
        raise NotImplementedError

class JsonFileSource(DataSource):
    """JSON 파일 데이터 소스"""
    
    def __init__(self, name: str, file_path: str):
        super().__init__(name, 'json')
        self.file_path = file_path
    
    async def collect_data(self) -> dict:
        """JSON 파일 데이터 수집"""
        try:
            if os.path.exists(self.file_path):
                async with aiofiles.open(self.file_path, 'r') as f:
                    content = await f.read()
                    return json.loads(content)
            return {}
        except Exception as e:
            logger.error(f"🔴 Failed to collect data from {self.file_path}: {e}")
            return {}
    
    async def restore_data(self, data: dict) -> bool:
        """JSON 파일 데이터 복원"""
        try:
            # 백업 생성
            if os.path.exists(self.file_path):
                backup_path = f"{self.file_path}.restore_backup"
                shutil.copy2(self.file_path, backup_path)
                logger.info(f"📋 Created restore backup: {backup_path}")
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            
            # 데이터 복원
            async with aiofiles.open(self.file_path, 'w') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            
            logger.info(f"✅ Restored data to {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"🔴 Failed to restore data to {self.file_path}: {e}")
            return False

class SQLiteSource(DataSource):
    """SQLite 데이터 소스"""
    
    def __init__(self, name: str, db_path: str, tables: List[str] = None):
        super().__init__(name, 'sqlite')
        self.db_path = db_path
        self.tables = tables or []
    
    async def collect_data(self) -> dict:
        """SQLite 데이터 수집"""
        try:
            if not os.path.exists(self.db_path):
                return {}
            
            # 단순히 파일 복사 (SQLite는 파일 기반)
            with open(self.db_path, 'rb') as f:
                return {
                    'database_file': f.read(),
                    'file_size': os.path.getsize(self.db_path)
                }
        except Exception as e:
            logger.error(f"🔴 Failed to collect SQLite data: {e}")
            return {}
    
    async def restore_data(self, data: dict) -> bool:
        """SQLite 데이터 복원"""
        try:
            if 'database_file' not in data:
                return False
            
            # 백업 생성
            if os.path.exists(self.db_path):
                backup_path = f"{self.db_path}.restore_backup"
                shutil.copy2(self.db_path, backup_path)
                logger.info(f"📋 Created restore backup: {backup_path}")
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # 데이터 복원
            with open(self.db_path, 'wb') as f:
                f.write(data['database_file'])
            
            logger.info(f"✅ Restored SQLite database to {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"🔴 Failed to restore SQLite database: {e}")
            return False

class BackupManager:
    """백업 관리자"""
    
    def __init__(self, backup_dir: str, max_backups: int = 30):
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.data_sources: Dict[str, DataSource] = {}
        self.backup_history: List[BackupMetadata] = []
        
        # 백업 디렉토리 생성
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 메타데이터 파일 경로
        self.metadata_file = self.backup_dir / "backup_metadata.json"
        
        # 메타데이터 로드
        self._load_metadata()
        
        logger.info(f"💾 Backup Manager initialized: {backup_dir} (max: {max_backups} backups)")
    
    def register_data_source(self, source: DataSource):
        """데이터 소스 등록"""
        self.data_sources[source.name] = source
        logger.info(f"📊 Data source '{source.name}' ({source.source_type}) registered")
    
    def register_json_source(self, name: str, file_path: str):
        """JSON 파일 소스 등록"""
        source = JsonFileSource(name, file_path)
        self.register_data_source(source)
    
    def register_sqlite_source(self, name: str, db_path: str):
        """SQLite 소스 등록"""
        source = SQLiteSource(name, db_path)
        self.register_data_source(source)
    
    async def create_backup(self, backup_type: BackupType = BackupType.FULL, 
                          compress: bool = True) -> Optional[BackupMetadata]:
        """백업 생성"""
        backup_id = self._generate_backup_id()
        timestamp = datetime.now().isoformat()
        
        metadata = BackupMetadata(
            backup_id=backup_id,
            timestamp=timestamp,
            backup_type=backup_type,
            status=BackupStatus.PENDING,
            file_path="",
            compression=compress
        )
        
        logger.info(f"🚀 Starting {backup_type.value} backup: {backup_id}")
        start_time = asyncio.get_event_loop().time()
        
        try:
            metadata.status = BackupStatus.RUNNING
            
            # 데이터 수집
            backup_data = {}
            for name, source in self.data_sources.items():
                logger.info(f"📊 Collecting data from source: {name}")
                source_data = await source.collect_data()
                backup_data[name] = {
                    'source_type': source.source_type,
                    'data': source_data
                }
            
            # 백업 파일 생성
            backup_filename = f"{backup_id}_{backup_type.value}_{timestamp.replace(':', '-')}.json"
            if compress:
                backup_filename += ".gz"
            
            backup_path = self.backup_dir / backup_filename
            metadata.file_path = str(backup_path)
            
            # 파일 저장
            backup_content = json.dumps({
                'metadata': {
                    'backup_id': backup_id,
                    'timestamp': timestamp,
                    'backup_type': backup_type.value,
                    'sources': list(self.data_sources.keys())
                },
                'data': backup_data
            }, indent=2, ensure_ascii=False)
            
            if compress:
                # 압축 저장
                backup_bytes = backup_content.encode('utf-8')
                with gzip.open(backup_path, 'wb') as f:
                    f.write(backup_bytes)
            else:
                # 일반 저장
                async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                    await f.write(backup_content)
            
            # 메타데이터 업데이트
            metadata.file_size = backup_path.stat().st_size
            metadata.checksum = await self._calculate_checksum(backup_path)
            metadata.status = BackupStatus.COMPLETED
            
            end_time = asyncio.get_event_loop().time()
            metadata.duration_seconds = end_time - start_time
            
            # 백업 히스토리에 추가
            self.backup_history.append(metadata)
            await self._save_metadata()
            
            # 오래된 백업 정리
            await self._cleanup_old_backups()
            
            logger.info(
                f"✅ Backup completed: {backup_id} "
                f"({metadata.file_size / 1024 / 1024:.2f} MB, {metadata.duration_seconds:.2f}s)"
            )
            
            return metadata
            
        except Exception as e:
            metadata.status = BackupStatus.FAILED
            metadata.error_message = str(e)
            
            end_time = asyncio.get_event_loop().time()
            metadata.duration_seconds = end_time - start_time
            
            self.backup_history.append(metadata)
            await self._save_metadata()
            
            logger.error(f"🔴 Backup failed: {backup_id}: {e}")
            return metadata
    
    async def restore_backup(self, backup_id: str) -> bool:
        """백업 복원"""
        logger.info(f"🔄 Starting restore from backup: {backup_id}")
        
        try:
            # 백업 메타데이터 찾기
            backup_metadata = None
            for metadata in self.backup_history:
                if metadata.backup_id == backup_id:
                    backup_metadata = metadata
                    break
            
            if not backup_metadata:
                logger.error(f"🔴 Backup not found: {backup_id}")
                return False
            
            if backup_metadata.status != BackupStatus.COMPLETED:
                logger.error(f"🔴 Backup is not completed: {backup_id} (status: {backup_metadata.status})")
                return False
            
            # 백업 파일 읽기
            backup_path = Path(backup_metadata.file_path)
            if not backup_path.exists():
                logger.error(f"🔴 Backup file not found: {backup_path}")
                return False
            
            # 체크섬 검증
            current_checksum = await self._calculate_checksum(backup_path)
            if current_checksum != backup_metadata.checksum:
                logger.error(f"🔴 Backup file checksum mismatch: {backup_id}")
                return False
            
            # 백업 파일 읽기
            if backup_metadata.compression:
                with gzip.open(backup_path, 'rt', encoding='utf-8') as f:
                    backup_content = f.read()
            else:
                async with aiofiles.open(backup_path, 'r', encoding='utf-8') as f:
                    backup_content = await f.read()
            
            backup_data = json.loads(backup_content)
            
            # 데이터 복원
            restored_count = 0
            for source_name, source_info in backup_data['data'].items():
                if source_name in self.data_sources:
                    logger.info(f"🔄 Restoring data source: {source_name}")
                    source = self.data_sources[source_name]
                    
                    if await source.restore_data(source_info['data']):
                        restored_count += 1
                        logger.info(f"✅ Restored data source: {source_name}")
                    else:
                        logger.error(f"🔴 Failed to restore data source: {source_name}")
                else:
                    logger.warning(f"⚠️ Data source not registered: {source_name}")
            
            logger.info(f"✅ Restore completed: {restored_count}/{len(backup_data['data'])} sources restored")
            return restored_count > 0
            
        except Exception as e:
            logger.error(f"🔴 Restore failed: {backup_id}: {e}")
            return False
    
    async def list_backups(self, limit: int = None) -> List[Dict[str, Any]]:
        """백업 목록 조회"""
        backups = sorted(self.backup_history, key=lambda b: b.timestamp, reverse=True)
        if limit:
            backups = backups[:limit]
        
        return [
            {
                'backup_id': b.backup_id,
                'timestamp': b.timestamp,
                'backup_type': b.backup_type.value,
                'status': b.status.value,
                'file_size_mb': b.file_size / 1024 / 1024,
                'duration_seconds': b.duration_seconds,
                'compression': b.compression,
                'checksum': b.checksum[:16] + "..." if b.checksum else ""
            }
            for b in backups
        ]
    
    async def delete_backup(self, backup_id: str) -> bool:
        """백업 삭제"""
        try:
            # 백업 메타데이터 찾기 및 제거
            backup_to_remove = None
            for i, metadata in enumerate(self.backup_history):
                if metadata.backup_id == backup_id:
                    backup_to_remove = metadata
                    del self.backup_history[i]
                    break
            
            if not backup_to_remove:
                logger.error(f"🔴 Backup not found for deletion: {backup_id}")
                return False
            
            # 백업 파일 삭제
            backup_path = Path(backup_to_remove.file_path)
            if backup_path.exists():
                backup_path.unlink()
                logger.info(f"🗑️ Deleted backup file: {backup_path}")
            
            # 메타데이터 저장
            await self._save_metadata()
            
            logger.info(f"✅ Backup deleted: {backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"🔴 Failed to delete backup {backup_id}: {e}")
            return False
    
    async def _cleanup_old_backups(self):
        """오래된 백업 정리"""
        if len(self.backup_history) <= self.max_backups:
            return
        
        # 타임스탬프 순으로 정렬
        sorted_backups = sorted(self.backup_history, key=lambda b: b.timestamp)
        
        # 제거할 백업들
        backups_to_remove = sorted_backups[:len(sorted_backups) - self.max_backups]
        
        for backup in backups_to_remove:
            await self.delete_backup(backup.backup_id)
        
        logger.info(f"🧹 Cleaned up {len(backups_to_remove)} old backups")
    
    def _generate_backup_id(self) -> str:
        """백업 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"backup_{timestamp}_{os.urandom(4).hex()}"
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """파일 체크섬 계산"""
        hash_sha256 = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    def _load_metadata(self):
        """메타데이터 로드"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                
                self.backup_history = [
                    BackupMetadata(
                        backup_id=item['backup_id'],
                        timestamp=item['timestamp'],
                        backup_type=BackupType(item['backup_type']),
                        status=BackupStatus(item['status']),
                        file_path=item['file_path'],
                        file_size=item.get('file_size', 0),
                        checksum=item.get('checksum', ''),
                        compression=item.get('compression', True),
                        duration_seconds=item.get('duration_seconds', 0.0),
                        error_message=item.get('error_message', '')
                    )
                    for item in data.get('backups', [])
                ]
                
                logger.info(f"📋 Loaded {len(self.backup_history)} backup records")
        except Exception as e:
            logger.error(f"🔴 Failed to load backup metadata: {e}")
            self.backup_history = []
    
    async def _save_metadata(self):
        """메타데이터 저장"""
        try:
            data = {
                'backups': [backup.to_dict() for backup in self.backup_history],
                'last_updated': datetime.now().isoformat()
            }
            
            async with aiofiles.open(self.metadata_file, 'w') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                
        except Exception as e:
            logger.error(f"🔴 Failed to save backup metadata: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """백업 관리자 상태 조회"""
        completed_backups = [b for b in self.backup_history if b.status == BackupStatus.COMPLETED]
        failed_backups = [b for b in self.backup_history if b.status == BackupStatus.FAILED]
        
        total_size = sum(b.file_size for b in completed_backups)
        
        return {
            'backup_dir': str(self.backup_dir),
            'max_backups': self.max_backups,
            'total_backups': len(self.backup_history),
            'completed_backups': len(completed_backups),
            'failed_backups': len(failed_backups),
            'total_size_mb': total_size / 1024 / 1024,
            'data_sources': len(self.data_sources),
            'data_source_names': list(self.data_sources.keys()),
            'last_backup': completed_backups[-1].timestamp if completed_backups else None
        }

# 글로벌 백업 매니저
backup_manager = BackupManager("./backups", max_backups=50)

# 테스트 함수
async def test_backup_manager():
    """Backup Manager 테스트"""
    print("🧪 Testing Backup Manager...")
    
    # 테스트용 JSON 파일 생성
    test_data = {'test': 'data', 'timestamp': datetime.now().isoformat()}
    test_file = './test_backup_data.json'
    
    with open(test_file, 'w') as f:
        json.dump(test_data, f)
    
    # 백업 매니저 설정
    test_manager = BackupManager("./test_backups", max_backups=5)
    test_manager.register_json_source("test_data", test_file)
    
    try:
        # 백업 생성
        backup = await test_manager.create_backup(BackupType.FULL, compress=True)
        if backup and backup.status == BackupStatus.COMPLETED:
            print(f"✅ Backup created: {backup.backup_id}")
            
            # 백업 목록 확인
            backups = await test_manager.list_backups(limit=5)
            print(f"📋 Found {len(backups)} backups")
            
            # 파일 수정
            modified_data = {'test': 'modified', 'timestamp': datetime.now().isoformat()}
            with open(test_file, 'w') as f:
                json.dump(modified_data, f)
            
            # 백업 복원
            if await test_manager.restore_backup(backup.backup_id):
                print("✅ Backup restored successfully")
                
                # 복원된 데이터 확인
                with open(test_file, 'r') as f:
                    restored_data = json.load(f)
                    if restored_data == test_data:
                        print("✅ Data integrity verified")
        
        # 상태 확인
        status = test_manager.get_status()
        print(f"📊 Backup Manager Status: {status['total_backups']} backups, {status['total_size_mb']:.2f} MB")
        
    finally:
        # 정리
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists("./test_backups"):
            shutil.rmtree("./test_backups")

if __name__ == "__main__":
    asyncio.run(test_backup_manager())