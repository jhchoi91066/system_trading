module.exports = {
  apps: [
    {
      name: 'trading-backend',
      script: 'python3',
      args: '-m uvicorn main:app --host 0.0.0.0 --port 8000',
      cwd: './backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PORT: 8000,
        PYTHONPATH: './backend'
      },
      error_file: './logs/backend-err.log',
      out_file: './logs/backend-out.log',
      log_file: './logs/backend-combined.log',
      time: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 2000,
      kill_timeout: 5000,
      listen_timeout: 8000,
      shutdown_with_message: true,
      // 헬스체크 추가
      health_check_url: 'http://localhost:8000/health'
    },
    {
      name: 'tradingview-webhook',
      script: '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3',
      args: 'tradingview_webhook.py',
      cwd: './backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        WEBHOOK_PORT: '8081',
        ENABLE_TRADINGVIEW: 'true',
        ENABLE_INTERNAL_CCI: 'false',
        ENABLE_EXTERNAL_CCI: 'false',
        SIGNAL_COOLDOWN: '30'
      },
      error_file: './logs/webhook-err.log',
      out_file: './logs/webhook-out.log',
      log_file: './logs/webhook-combined.log',
      time: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 2000,
      kill_timeout: 5000,
      shutdown_with_message: true
    },
    {
      name: 'health-monitor',
      script: '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3',
      args: 'health_monitor.py',
      cwd: '.',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      error_file: './logs/health-monitor-err.log',
      out_file: './logs/health-monitor-out.log',
      log_file: './logs/health-monitor-combined.log',
      time: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      max_restarts: 5,
      min_uptime: '10s',
      restart_delay: 5000,
      kill_timeout: 5000,
      shutdown_with_message: true
    }
  ]
};