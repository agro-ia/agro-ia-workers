import investpy
import pandas as pd
import warnings

# Suppress the specific pkg_resources warning if it appears
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")

def list_all_commodities():
    print("--- Fetching Commodities List from investpy ---")
    
    try:
        # get_commodities returns a pandas DataFrame with columns: 
        # ['country', 'name', 'full_name', 'symbol', 'currency', 'id', 'group']
        df = investpy.get_commodities()
        
        total_count = len(df)
        print(f"✅ Successfully retrieved {total_count} commodities.")
        
        # Display a sample of the data
        print("\n--- Sample Data (First 5) ---")
        print(df[['name', 'country', 'currency', 'group']].head().to_string(index=False))
        
        # Save to CSV for full inspection
        output_file = 'investpy_commodities_list.csv'
        df.to_csv(output_file, index=False)
        print(f"\n💾 Full list saved to: {output_file}")

        # df = investpy.get_etfs()
        # total_count = len(df)
        # print(f"✅ Successfully retrieved {total_count} etfs.")

        # output_file = 'investpy_etfs_list.csv'
        # df.to_csv(output_file, index=False)
        # print(f"\n💾 Full list saved to: {output_file}")
        
        return df

    except Exception as e:
        print(f"❌ Error retrieving commodities: {e}")
        return None

if __name__ == "__main__":
    # Retrieve the list
    df_commodities = list_all_commodities()
    
    # Optional: Print all unique groups (e.g., metals, energy, softs)
    if df_commodities is not None:
        print("\n--- Commodity Groups Available ---")
        print(df_commodities['group'].unique())