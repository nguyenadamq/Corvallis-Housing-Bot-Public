from bs4 import BeautifulSoup #Scrape website
from selenium import * #Opens links and bypasses some anti bot pretection
import requests #Pull duerksen api
from datetime import datetime
from fake_useragent import UserAgent
import re # Text matching
import time
from discord_webhook import DiscordWebhook, DiscordEmbed
API_URL = "https://www.duerksenrentals.com/rts/collections/public/641c13fd/runtime/collection/appfolio-listings/data?page=%7B%22pageSize%22%3A100%2C%22pageNumber%22%3A0%7D&language=ENGLISH"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Referer": "https://www.duerksenrentals.com/vacancies",
    "Accept": "application/json"
}
FILTERED_DISCORD_URL = ""
DISCORD_URL = ""

#Rentals array ["address", price/month, Beds, Baths, Sqft, "Move in Date", "URL"]
rentals = []
existing_addresses = []
existing_listings = []
new_listings = []
filtered_listings = []
listings = []

def uid_to_url(uid):
    url = "https://www.duerksenrentals.com/listings/detail/" + str(uid)
    return url

#Function that pulls from api and converts into listings list
def fetch_listings():
    response = requests.get(API_URL, headers=HEADERS, timeout=10)
    while True:
        for attempt in range(1, 6):
            try:
                response = requests.get(API_URL, headers=HEADERS, timeout=10)
                print("API placed in response.")
                print(f"API Response: {response.status_code}", flush=True)
                response.raise_for_status() #Raises error if not successful
                print("Request successful. Continuing...")
                data = response.json()
                listings = data.get("values", []) #Extracts the data from json response
                return [listing["data"] for listing in listings]
    
            except requests.exceptions.RequestException as e:
                print(f"[Attempt: {attempt}] Failed to load URL: {e}")
                if attempt < 5:
                    print(f"Retrying for 10 seconds before retrying again...")
                    time.sleep(10)
                else:
                    print("Due to failed attempts, waiting 1 hour before retrying...")
                    message = "Due to failed attempts at accessing api URL, waiting 1 hour before retrying...: " + str(time())
                    webhook = DiscordWebhook(url=DISCORD_URL, content=message)
                    try:
                        webhook.execute()
                        print("Sent notification in Discord!")
                    except Exception as e:
                        print(f"Failed to send Discord notication: {e}")
                    time.sleep(3600)

#Takes listings and puts into array
def listing_data_to_rentals_array(listings):
    #Iterate through listings array
    for listing in listings:
        #Pull from api values
        address = str(listing.get("full_address"))
        price = str(listing.get("market_rent"))
        beds = str(listing.get("bedrooms"))
        baths = str(listing.get("bathrooms"))
        sqft = str(listing.get("square_feet", "Not listed"))
        uid = listing.get("listable_uid")
        move_in = listing.get("available_date")
        url = str(uid_to_url(uid))
        photo_url = str(listing.get("default_photo_thumbnail_url"))

        if "Apartment" in str(listing.get("marketing_title")):
            housing_type = "Apartment"
        elif "Duplex" in str(listing.get("marketing_title")):
            housing_type = "Duplex"
        elif "Townhouse" in str(listing.get("marketing_title")):
            housing_type = "Townhouse"
        elif " House " in str(listing.get("marketing_title")):
            housing_type = "House"
        else:
            housing_type = ""
        #Append to rentals
        rental = [address, price, beds, baths, sqft, move_in, url, photo_url, housing_type]
        if (rental not in existing_listings) and ("corvallis" in str(address).lower()):
            new_listings.append(rental)
            existing_listings.append(rental)
    return

# def push_to_sheet(rentals):
    sheet = client.open("Duerksen Listings").sheet1
    sheet.append_rows(rentals, 2)
    return

def discord_notification(new_listings, beds, baths, price, filtersqft, housing_type):
    if(FILTERED_DISCORD_URL and DISCORD_URL):

        filter_message = "**Current filter: **\n"
        filter_message += "Beds: **" + str(beds) + "**\n"
        filter_message += "Baths: **" + str(baths) + "**\n"
        filter_message += "Price under: **" + str(price) + "**\n"
        if housing_type == 1:
            filter_message += "Housing type includes: **Houses, Townhouses, and Duplexes**\n"
        else:
            filter_message += "Housing type includes: **Houses, Townhouses, Duplexes, and Apartments**\n"
        filter_message += "Sqft over: " + str(filtersqft) + "\n"
        time.sleep(3)
        webhook = DiscordWebhook(url=FILTERED_DISCORD_URL, content=filter_message)
        
        try:
            webhook.execute()
            print("Sent notification in Discord!")
        except Exception as e:
            print(f"Failed to send Discord notication: {e}")
        message = ""
        for listing in new_listings:
            time.sleep(3)
            current_housing_search = True
            if housing_type == 1 and str(listing[8]) == "Apartment":
                current_housing_search = False
            
            #Turn sqft from string to just the number for filtering
            sqft = re.match(r'\d+', listing[4])
            if sqft:
                sqft = sqft.group(0)
            #(float(listing[2]) >= float(beds)) and (float(listing[3]) >= float(baths)) and (float(listing[1]) < float(price)) and (float(sqft) >= float(filtersqft) and (current_housing_search == True)):
            #Visualize price filter match
            if (float(listing[1]) < float(price)):
                message += "Price: " + "$" + "**" + str(listing[1]) + "** a month      ✅\n"
            else:
                message += "Price: " + "$" + "**" + str(listing[1]) + "** a month      ❌\n"

            #Max the beds and baths(visual filter)
            if (float(listing[2]) >= float(beds)) and (float(listing[3]) < float(baths)):
                message += "Beds/Baths: " + "**" + str(listing[2]) + "✅/" + str(listing[3]) + "     ❌**\n"
            elif (float(listing[2]) < float(beds)) and (float(listing[3]) < float(baths)):
                message += "Beds/Baths: " + "**" + str(listing[2]) + "❌/" + str(listing[3]) + "     ❌**\n"
            elif (float(listing[2]) < float(beds)) and (float(listing[3]) >= float(baths)):
                message += "Beds/Baths: " + "**" + str(listing[2]) + "❌/" + str(listing[3]) + "     ✅**\n"
            else:
                message += "Beds/Baths: " + "**" + str(listing[2]) + "✅/" + str(listing[3]) + "     ✅**\n"
            if sqft:
                if (float(sqft) >= float(filtersqft)):
                    message += "Square Feet: " + "**" + str(listing[4]) + "     ✅**\n"
                else:
                    message += "Square Feet: " + "**" + str(listing[4]) + "     ❌**\n"
            else:
                message += "Square Feet: " + "**None     ❌**\n"
            
            message += "Move-in Date: " + "**" + str(listing[5]) + "**\n"
            if (current_housing_search == True):
                message += "Housing type: " + "**" + str(listing[8]) + "     ✅**\n"
            else:
                message += "Housing type: " + "**" + str(listing[8]) + "     ❌**\n"
            embed = DiscordEmbed(title=str(listing[0]), description=message)
            
            
            #Set the image to have the info
            embed.set_image(url=str(listing[7]))
            embed.add_embed_field(name="", value = f"[Listing Link](https://www.{str(listing[6])})")
            webhook = DiscordWebhook(url=DISCORD_URL)
            webhook.add_embed(embed)
            try:
                webhook.execute()
                print("Sent notification in Discord!")
            except Exception as e:
                print(f"Failed to send Discord notication: {e}")
            message = ""
            
            #Turn sqft from string to just the number for filtering
            sqft = re.match(r'\d+', listing[4])
            if sqft:
                sqft = sqft.group(0)
                #Append to filtered listings if match the search
                if (float(listing[2]) >= float(beds)) and (float(listing[3]) >= float(baths)) and (float(listing[1]) < float(price)) and (current_housing_search == True):
                    #Set the image to have the info
                    time.sleep(3)
                    embed.set_image(url=str(listing[7]))
                    # embed.add_embed_field(name="", value = f"[Listing Link](https://www.{str(listing[6])})")
                    webhook = DiscordWebhook(url=FILTERED_DISCORD_URL)
                    webhook.add_embed(embed)
        
                    try:
                        webhook.execute()
                        print("Sent filtered notification in Discord!")
                    except Exception as e:
                        print(f"Failed to send Discord notication: {e}")
            else:
                #Append to filtered listings if match the search
                if (float(listing[2]) >= float(beds)) and (float(listing[3]) >= float(baths)) and (float(listing[1]) < float(price)) and (current_housing_search == True):
                    #Set the image to have the info
                    time.sleep(3)
                    embed.set_image(url=str(listing[7]))
                    # embed.add_embed_field(name="", value = f"[Listing Link](https://www.{str(listing[6])})")
                    webhook = DiscordWebhook(url=FILTERED_DISCORD_URL)
                    webhook.add_embed(embed)
        
                    try:
                        webhook.execute()
                        print("Sent filtered notification in Discord!")
                    except Exception as e:
                        print(f"Failed to send Discord notication: {e}")
        return
    else:
        print("New Listings Found: \n")
        for listing in new_listings:
            print(f"Address: {listing[0]}, Link: {listing[6]}")

def main():
    #Get filtered results
    listings = fetch_listings() #Grab listings from API
    listing_data_to_rentals_array(listings) #Turn listings into array
    
    return new_listings
#Main python run
if __name__ == "__main__":
    DISCORD_USED = False
    #Get filtered user input for separate discord channel
    while True:
        min_beds = input("\nWhats your minimum number of beds?\n")
        if min_beds.isdigit() and int(min_beds) > 0:
            min_beds = int(min_beds)
            break
        else: 
            print("Invalid input. Please try again.")
    while True:
        min_baths = input("\nWhats your minimum number of baths?\n")
        if min_baths.isdigit() and int(min_baths) > 0:
            min_baths = int(min_baths)
            break
        else: 
            print("Invalid input. Please try again.")
    while True:
        max_price = input("\nWhats your maximum price per month?\n")
        if max_price.isdigit() and int(max_price) > 0:
            max_price = int(max_price)
            break
        else: 
            print("Invalid input. Please try again.")
    while True:
        min_sqft = input("\nWhats your minimum number of sqft?\n")
        if min_sqft.isdigit() and int(min_sqft) > 0:
            min_sqft = int(min_sqft)
            break
        else: 
            print("Invalid input. Please try again.")
    while True:
        housing_type = input("\nWhats your preffered housing type? (1)House, Townhouse, Duplex, (2)Include Apartments\n")
        if housing_type.isdigit() and int(housing_type) > 0 and int(housing_type) <= 2:
            housing_type = int(housing_type)
            break
        else: 
            print("Invalid input. Please try again.")
    while True:
        DISCORD_USED = input("\nWould you like to send new_listings to your discord for notifications?(Yes: Y/y, No: N/n): ")
        if(DISCORD_USED.lower() == 'y'):
            DISCORD_USED = True
            break
        elif(DISCORD_USED.lower() == 'n'):
            DISCORD_USED = False
            break
        else:
            print("Invalid input. Please try again.")
    if(DISCORD_USED == True):
        print(DISCORD_USED)
        while True:
            DISCORD_URL = input("\nWhat discord webhook do you want to be notified for all listings?\n")
            if(DISCORD_URL):
                try:
                    response = requests.get(DISCORD_URL)
                    if(DISCORD_URL and (response.status_code == 200)):
                        print("Valid webhook")
                        break
                    else:
                        print("Invalid url. Please try again.")
                except requests.exceptions.MissingSchema:
                    print("URL format invalid (missing http/https schema)")
                    False
                except requests.exceptions.ConnectionError as e:
                    print(f"Connection error: {e}")
                except Exception as e:
                    print(f"Unexpected error occured: {e}")
            else:
                print("Empty input. Please input the webhook url")

        while True:
            FILTERED_DISCORD_URL = input("\nWhat discord webhook do you want to be notified for filtered listings?\n")
            if(FILTERED_DISCORD_URL):
                try:
                    response = requests.get(DISCORD_URL)
                    if(DISCORD_URL and (response.status_code == 200)):
                        print("Valid webhook")
                        break
                    else:
                        print("Invalid url. Please try again.")
                except requests.exceptions.MissingSchema:
                    print("URL format invalid (missing http/https schema)")
                    False
                except requests.exceptions.ConnectionError as e:
                    print(f"Connection error: {e}")
                except Exception as e:
                    print(f"Unexpected error occured: {e}")
            else:
                print("Empty input. Please input the webhook url")

    while True:
        print("Searching for new listings...")
        new_listings = main()

        #New listings
        if len(new_listings) < 1:
            print("No new listings.")
        else:
            #Discord message
            discord_notification(new_listings, min_beds, min_baths, max_price, min_sqft, housing_type) #all new listings channel
            new_listings = [] #Clear new listings after discord message sent
        print("Rechecking again in 3 hours...")
        time.sleep(10800) # Run every 3 hours
        

    
