import requests
import datetime
import os

def send_report_request():
    """
    Sends a POST request to the reporting API to generate a daily report.
    """
    # Get the current date
    target_date = datetime.date.today().strftime('%Y-%m-%d')

    # The endpoint for generating the report
    # Use the environment variable 'BASE_URL' if available, otherwise default to localhost
    base_url = os.getenv('BASE_URL', 'https://zenfru-agent.onrender.com')
    url = f"{base_url}/api/generate_report"

    # The data to be sent in the request body
    payload = {
        "target_date": target_date,
        "send_email": True
    }

    try:
        print(f"Sending request to {url} with payload: {payload}")
        response = requests.post(url, json=payload, timeout=300) # 5 minute timeout
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        print("Successfully triggered report generation.")
        print("Response:", response.json())

    except requests.exceptions.RequestException as e:
        print(f"Error sending request: {e}")

if __name__ == "__main__":
    # send_report_request()  # Disabled to prevent sending the report request
    pass