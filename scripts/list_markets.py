from blocky import Blocky

API_ENDPOINT = "https://craft.blocky.com.br/api/v1"
client = Blocky(endpoint=API_ENDPOINT)

print(f"Fetching markets from {API_ENDPOINT}...")
try:
    response = client.get_markets()
    if response.get("success"):
        print("\nAvailable Markets:")
        for market in response.get("markets", []):
            print(f"- {market['market']} (Base: {market.get('base_instrument')}, Quote: {market.get('quote_instrument')})")
    else:
        print("Failed to fetch markets:", response)
except Exception as e:
    print(f"Error: {e}")
