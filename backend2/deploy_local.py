"""
Local deployment script for BrightSmile Dental AI Assistant
Starts the FastAPI server and creates an ngrok tunnel
"""

import subprocess
import time
import sys
import os
from pathlib import Path

def start_fastapi_server():
    """Start the FastAPI server in background"""
    print("🚀 Starting FastAPI server...")
    
    # Change to backend2 directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    # Start FastAPI server
    process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", 
        "main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--reload"
    ])
    
    print("✅ FastAPI server started on http://localhost:8000")
    return process

def start_ngrok_tunnel():
    """Start ngrok tunnel"""
    print("🌐 Starting ngrok tunnel...")
    
    # Start ngrok tunnel
    process = subprocess.Popen([
        "ngrok", "http", "8000",
        "--log", "stdout"
    ])
    
    print("✅ Ngrok tunnel started!")
    print("📋 Check ngrok dashboard at: http://localhost:4040")
    print("🔗 Your API will be available at the ngrok URL")
    
    return process

def main():
    print("🦷 BrightSmile Dental AI Assistant - Local Deployment")
    print("=" * 60)
    
    try:
        # Start FastAPI server
        fastapi_process = start_fastapi_server()
        
        # Wait a bit for server to start
        print("⏳ Waiting for server to start...")
        time.sleep(3)
        
        # Start ngrok tunnel
        ngrok_process = start_ngrok_tunnel()
        
        print("\n" + "=" * 60)
        print("🎉 Deployment successful!")
        print("📊 Services running:")
        print("   - FastAPI Server: http://localhost:8000")
        print("   - Ngrok Dashboard: http://localhost:4040")
        print("   - API Documentation: http://localhost:8000/docs")
        print("\n💡 Your API is now accessible from anywhere via ngrok URL!")
        print("📱 Perfect for testing with AI voice assistants and mobile apps")
        print("\n⚠️  Press Ctrl+C to stop all services")
        
        # Wait for user to stop
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping services...")
            fastapi_process.terminate()
            ngrok_process.terminate()
            print("✅ All services stopped!")
            
    except Exception as e:
        print(f"❌ Error during deployment: {e}")

if __name__ == "__main__":
    main()
