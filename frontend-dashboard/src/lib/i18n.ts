import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Translation resources
const resources = {
  en: {
    translation: {
      // Navigation
      'nav.dashboard': 'Dashboard',
      'nav.strategies': 'Strategies',
      'nav.apiKeys': 'API Keys',
      'nav.monitoring': 'Monitoring',
      'nav.notifications': 'Notifications',
      'nav.signIn': 'Sign In',
      'nav.signUp': 'Sign Up',
      
      // Dashboard
      'dashboard.title': 'Bitcoin Trading',
      'dashboard.subtitle': 'Advanced cryptocurrency trading dashboard with backtesting and real-time data',
      'dashboard.welcome': 'Welcome to Bitcoin Trading Dashboard',
      'dashboard.selectExchange': 'Select Exchange',
      'dashboard.selectSymbol': 'Select Symbol',
      'dashboard.loadData': 'Load Data',
      'dashboard.currentPrice': 'Current Price',
      'dashboard.change24h': '24h Change',
      'dashboard.volume': 'Volume',
      'dashboard.marketCap': 'Market Cap',
      
      // Trading Chart
      'chart.title': 'Chart',
      'chart.loading': 'Loading chart data...',
      'chart.error': 'Error loading chart data',
      'chart.retry': 'Retry',
      'chart.timeframe': 'Timeframe',
      'chart.indicators': 'Indicators',
      'chart.lastUpdated': 'Last updated',
      
      // Strategies
      'strategies.title': 'Trading Strategies',
      'strategies.create': 'Create Strategy',
      'strategies.name': 'Strategy Name',
      'strategies.description': 'Description',
      'strategies.type': 'Type',
      'strategies.parameters': 'Parameters',
      'strategies.backtest': 'Backtest',
      'strategies.activate': 'Activate',
      'strategies.deactivate': 'Deactivate',
      'strategies.performance': 'Performance',
      'strategies.winRate': 'Win Rate',
      'strategies.totalTrades': 'Total Trades',
      
      // API Keys
      'apiKeys.title': 'API Key Management',
      'apiKeys.add': 'Add API Key',
      'apiKeys.exchange': 'Exchange',
      'apiKeys.apiKey': 'API Key',
      'apiKeys.secretKey': 'Secret Key',
      'apiKeys.status': 'Status',
      'apiKeys.active': 'Active',
      'apiKeys.inactive': 'Inactive',
      'apiKeys.test': 'Test Connection',
      'apiKeys.delete': 'Delete',
      
      // Monitoring
      'monitoring.title': 'Real-time Monitoring',
      'monitoring.portfolio': 'Portfolio Overview',
      'monitoring.totalCapital': 'Total Capital',
      'monitoring.allocated': 'Allocated',
      'monitoring.available': 'Available',
      'monitoring.activeStrategies': 'Active Strategies',
      'monitoring.recentTrades': 'Recent Trades',
      'monitoring.systemStatus': 'System Status',
      'monitoring.online': 'Online',
      'monitoring.offline': 'Offline',
      
      // Notifications
      'notifications.title': 'Notifications',
      'notifications.markAllRead': 'Mark All Read',
      'notifications.filter.all': 'All',
      'notifications.filter.unread': 'Unread',
      'notifications.filter.trade': 'Trade',
      'notifications.filter.risk': 'Risk',
      'notifications.filter.system': 'System',
      'notifications.priority.low': 'Low',
      'notifications.priority.medium': 'Medium',
      'notifications.priority.high': 'High',
      'notifications.priority.critical': 'Critical',
      
      // Common
      'common.save': 'Save',
      'common.cancel': 'Cancel',
      'common.delete': 'Delete',
      'common.edit': 'Edit',
      'common.loading': 'Loading...',
      'common.error': 'Error',
      'common.success': 'Success',
      'common.warning': 'Warning',
      'common.info': 'Info',
      'common.refresh': 'Refresh',
      'common.settings': 'Settings',
      'common.language': 'Language',
      
      // Status Messages
      'status.connected': 'Connected',
      'status.disconnected': 'Disconnected',
      'status.connecting': 'Connecting...',
      'status.error': 'Connection Error',
      
      // Forms
      'form.required': 'This field is required',
      'form.invalid': 'Invalid input',
      'form.submit': 'Submit',
      'form.reset': 'Reset',
    }
  },
  ko: {
    translation: {
      // Navigation
      'nav.dashboard': '대시보드',
      'nav.strategies': '전략',
      'nav.apiKeys': 'API 키',
      'nav.monitoring': '모니터링',
      'nav.notifications': '알림',
      'nav.signIn': '로그인',
      'nav.signUp': '회원가입',
      
      // Dashboard
      'dashboard.title': '비트코인 트레이딩',
      'dashboard.subtitle': '백테스팅과 실시간 데이터를 제공하는 고급 암호화폐 거래 대시보드',
      'dashboard.welcome': '비트코인 트레이딩 대시보드에 오신 것을 환영합니다',
      'dashboard.selectExchange': '거래소 선택',
      'dashboard.selectSymbol': '심볼 선택',
      'dashboard.loadData': '데이터 로드',
      'dashboard.currentPrice': '현재 가격',
      'dashboard.change24h': '24시간 변동',
      'dashboard.volume': '거래량',
      'dashboard.marketCap': '시가총액',
      
      // Trading Chart
      'chart.title': '차트',
      'chart.loading': '차트 데이터 로딩 중...',
      'chart.error': '차트 데이터 로딩 오류',
      'chart.retry': '다시 시도',
      'chart.timeframe': '시간대',
      'chart.indicators': '지표',
      'chart.lastUpdated': '마지막 업데이트',
      
      // Strategies
      'strategies.title': '거래 전략',
      'strategies.create': '전략 생성',
      'strategies.name': '전략명',
      'strategies.description': '설명',
      'strategies.type': '유형',
      'strategies.parameters': '매개변수',
      'strategies.backtest': '백테스트',
      'strategies.activate': '활성화',
      'strategies.deactivate': '비활성화',
      'strategies.performance': '성과',
      'strategies.winRate': '승률',
      'strategies.totalTrades': '총 거래수',
      
      // API Keys
      'apiKeys.title': 'API 키 관리',
      'apiKeys.add': 'API 키 추가',
      'apiKeys.exchange': '거래소',
      'apiKeys.apiKey': 'API 키',
      'apiKeys.secretKey': '시크릿 키',
      'apiKeys.status': '상태',
      'apiKeys.active': '활성',
      'apiKeys.inactive': '비활성',
      'apiKeys.test': '연결 테스트',
      'apiKeys.delete': '삭제',
      
      // Monitoring
      'monitoring.title': '실시간 모니터링',
      'monitoring.portfolio': '포트폴리오 개요',
      'monitoring.totalCapital': '총 자본',
      'monitoring.allocated': '할당됨',
      'monitoring.available': '사용 가능',
      'monitoring.activeStrategies': '활성 전략',
      'monitoring.recentTrades': '최근 거래',
      'monitoring.systemStatus': '시스템 상태',
      'monitoring.online': '온라인',
      'monitoring.offline': '오프라인',
      
      // Notifications
      'notifications.title': '알림',
      'notifications.markAllRead': '모두 읽음으로 표시',
      'notifications.filter.all': '전체',
      'notifications.filter.unread': '읽지 않음',
      'notifications.filter.trade': '거래',
      'notifications.filter.risk': '위험',
      'notifications.filter.system': '시스템',
      'notifications.priority.low': '낮음',
      'notifications.priority.medium': '보통',
      'notifications.priority.high': '높음',
      'notifications.priority.critical': '긴급',
      
      // Common
      'common.save': '저장',
      'common.cancel': '취소',
      'common.delete': '삭제',
      'common.edit': '편집',
      'common.loading': '로딩 중...',
      'common.error': '오류',
      'common.success': '성공',
      'common.warning': '경고',
      'common.info': '정보',
      'common.refresh': '새로고침',
      'common.settings': '설정',
      'common.language': '언어',
      
      // Status Messages
      'status.connected': '연결됨',
      'status.disconnected': '연결 끊김',
      'status.connecting': '연결 중...',
      'status.error': '연결 오류',
      
      // Forms
      'form.required': '필수 입력 항목입니다',
      'form.invalid': '잘못된 입력입니다',
      'form.submit': '제출',
      'form.reset': '재설정',
    }
  }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    debug: process.env.NODE_ENV === 'development',
    
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'i18nextLng',
      caches: ['localStorage'],
    },
    
    interpolation: {
      escapeValue: false, // React already does escaping
    },
    
    react: {
      useSuspense: false,
    },
    
    // SSR 호환성을 위한 설정
    initImmediate: false,
    load: 'languageOnly',
  });

export default i18n;