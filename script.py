# Let's create the comprehensive crypto trading system structure
import os
import json

# Create the main project structure
project_structure = {
    'crypto_trading_system/': {
        '__init__.py': '',
        'config/': {
            '__init__.py': '',
            'config.py': '',
            'binance_config.py': '',
            '.env.example': ''
        },
        'data/': {
            '__init__.py': '',
            'data_manager.py': '',
            'websocket_client.py': '',
            'historical_data.py': ''
        },
        'strategies/': {
            '__init__.py': '',
            'base_strategy.py': '',
            'momentum_strategy.py': '',
            'mean_reversion_strategy.py': '',
            'grid_strategy.py': ''
        },
        'risk/': {
            '__init__.py': '',
            'risk_manager.py': '',
            'portfolio_manager.py': ''
        },
        'execution/': {
            '__init__.py': '',
            'order_manager.py': '',
            'execution_engine.py': ''
        },
        'backtesting/': {
            '__init__.py': '',
            'backtest_engine.py': '',
            'performance_metrics.py': ''
        },
        'database/': {
            '__init__.py': '',
            'db_manager.py': '',
            'models.py': ''
        },
        'monitoring/': {
            '__init__.py': '',
            'dashboard.py': '',
            'alerts.py': '',
            'logger.py': ''
        },
        'utils/': {
            '__init__.py': '',
            'helpers.py': '',
            'indicators.py': ''
        },
        'main.py': '',
        'requirements.txt': '',
        'docker-compose.yml': '',
        'Dockerfile': '',
        'README.md': ''
    }
}

def create_directory_structure(structure, base_path=''):
    """Create the directory structure with files"""
    for name, content in structure.items():
        path = os.path.join(base_path, name)
        if isinstance(content, dict):
            # It's a directory
            os.makedirs(path, exist_ok=True)
            create_directory_structure(content, path)
        else:
            # It's a file
            with open(path, 'w') as f:
                f.write(content)

# Create the structure
create_directory_structure(project_structure)
print("✅ Project structure created successfully!")
print("\n📁 Directory structure:")
for root, dirs, files in os.walk('crypto_trading_system'):
    level = root.replace('crypto_trading_system', '').count(os.sep)
    indent = ' ' * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = ' ' * 2 * (level + 1)
    for file in files:
        print(f"{subindent}{file}")