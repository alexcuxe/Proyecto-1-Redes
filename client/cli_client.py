# Minimal host CLI to interact with the server and log interactions.
# This also helps classmates test your server easily.
import argparse, json
from stdio_client import StdioClient

def main():
    p = argparse.ArgumentParser(description="BearingPro-MCP CLI host")
    p.add_argument("--method", required=True, choices=["catalog_list","select_bearing","verify_point","ping"])
    p.add_argument("--params", default="{}", help='JSON string of params, e.g. {"rpm":1800,"Fr_N":3500,"Fa_N":1200}')
    args = p.parse_args()

    client = StdioClient()
    try:
        params = json.loads(args.params)
        resp = client.call(args.method, params)
        print(json.dumps(resp, indent=2, ensure_ascii=False))
    finally:
        client.close()

if __name__ == "__main__":
    main()
