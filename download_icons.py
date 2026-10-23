import urllib.request
import json
import os

target_dir = os.path.join("..", "masterstrokefrontend", "public", "icons", "3d")
os.makedirs(target_dir, exist_ok=True)

# List of icon mappings: (filename, asset_folder, subfolder_or_name)
# In microsoft/fluentui-emoji, assets are organized under assets/<Name>/3D/<name_3d.png>
# Or assets/<Name>/Default/3D/<name_3d_default.png>

emojis = [
    # Category icons
    ("my_business.png", "Convenience store/3D/convenience_store_3d.png"),
    ("b2b_trade.png", "Handshake/3D/handshake_3d.png"),
    ("doctors.png", "Health worker/Default/3D/health_worker_3d_default.png"),
    ("travel.png", "Airplane/3D/airplane_3d.png"),
    ("beauty.png", "Lotus/3D/lotus_3d.png"),
    ("weddings.png", "Ring/3D/ring_3d.png"),
    ("fitness.png", "Dumbbell/3D/dumbbell_3d.png"),
    ("education.png", "Graduation cap/3D/graduation_cap_3d.png"),
    ("packers.png", "Delivery truck/3D/delivery_truck_3d.png"),
    ("repairs.png", "Wrench/3D/wrench_3d.png"),
    ("rent.png", "Key/3D/key_3d.png"),
    ("jobs.png", "Busts in silhouette/3D/busts_in_silhouette_3d.png"),
    ("finance.png", "Coin/3D/coin_3d.png"),
    ("real_estate.png", "House with garden/3D/house_with_garden_3d.png"),
    ("hostels.png", "Bed/3D/bed_3d.png"),
    ("show_more.png", "Sparkles/3D/sparkles_3d.png"),
    
    # Overview / Portal / Navigation icons
    ("gift_box.png", "Wrapped gift/3D/wrapped_gift_3d.png"),
    ("star.png", "Star/3D/star_3d.png"),
    ("user_avatar.png", "Bust in silhouette/3D/bust_in_silhouette_3d.png"),
    ("shopping_bag.png", "Shopping bags/3D/shopping_bags_3d.png"),
    ("money_bag.png", "Money bag/3D/money_bag_3d.png"),
    ("trophy.png", "Trophy/3D/trophy_3d.png"),
    ("party_popper.png", "Party popper/3D/party_popper_3d.png"),
    ("bell.png", "Bell/3D/bell_3d.png"),
]

base_url = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/"

for fname, rel_path in emojis:
    out_path = os.path.join(target_dir, fname)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        print(f"Already exists: {fname}")
        continue
    
    url = base_url + urllib.parse.quote(rel_path)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            data = response.read()
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"Downloaded {fname} ({len(data)} bytes)")
    except Exception as e:
        print(f"Failed {fname} from {url}: {e}")
        # Try fallback if default subfolder difference
