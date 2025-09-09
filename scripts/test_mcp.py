import requests
import json

def test_mcp_endpoint():
    url = "http://localhost:8080/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "search_tickets",
        "params": {"query": "", "page": 1}
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print("\nAvailable MCP Tools:")
        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                print(json.dumps(result['result'], indent=2))
            else:
                print(json.dumps(result, indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_mcp_endpoint()
