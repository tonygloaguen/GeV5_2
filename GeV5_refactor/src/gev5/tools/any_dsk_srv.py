import subprocess
import time

# Avant toute chose : wget -qO - https://keys.anydesk.com/repos/DEB-GPG-KEY | sudo apt-key add -
# echo "deb http://deb.anydesk.com/ all main" | sudo tee /etc/apt/sources.list.d/anydesk.list
# sudo apt update
# sudo apt install anydesk

class AnyDeskServer:
    def __init__(self):
        self.anydesk_path = "/usr/bin/rustdesk"
    
    def start_anydesk(self):
        """Start the RustDesk server"""
        try:
            subprocess.run([self.anydesk_path], check=True)
            print("AnyDesk started successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to start AnyDesk: {e}")
    
    def stop_anydesk(self):
        """Stop the RustDesk server"""
        try:
            subprocess.run(["pkill", "RustDesk"], check=True)
            print("RustDesk stopped successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to stop AnyDesk: {e}")
    
    def is_anydesk_running(self):
        """Check if RustDesk is running"""
        try:
            output = subprocess.check_output(["pgrep", "-f", "RustDesk"])
            if output:
                print("RustDesk is running.")
                return True
        except subprocess.CalledProcessError:
            print("RustDesk is not running.")
            return False

if __name__ == "__main__":
    anydesk_server = AnyDeskServer()
    
    # Example usage
    anydesk_server.start_anydesk()
    time.sleep(5)  # Wait for 5 seconds
    running = anydesk_server.is_anydesk_running()
    if running:
        print("RustDesk is up and running!")
    else:
        print("RustDesk failed to start.")
    
    # Stop AnyDesk after 10 seconds for demonstration
    time.sleep(10)
    anydesk_server.stop_anydesk()
