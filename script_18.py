# Check what's in the current directory
import os
print("Current directory:", os.getcwd())
print("Files and directories in current location:")
for item in os.listdir('.'):
    print(f"  {item}")
    
# The system was created earlier, let's verify it exists
if 'crypto_trading_system' in os.listdir('.'):
    print("\n✅ Found crypto_trading_system directory!")
    print("Contents:")
    for root, dirs, files in os.walk('crypto_trading_system'):
        level = root.replace('crypto_trading_system', '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files[:10]:  # Limit to first 10 files per directory
            print(f"{subindent}{file}")
        if len(files) > 10:
            print(f"{subindent}... and {len(files)-10} more files")
else:
    print("❌ crypto_trading_system directory not found. Let's create the final structure.")