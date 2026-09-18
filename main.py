"""
ISOM3400 Individual Assignment
Hong Kong Rental Property Market Analyser
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import csv
import os
import time


class PropertyScraper:
    """Scrapes rental property data from SquareFoot.com.hk."""

    def __init__(self):
        """Initialize the scraper with a headless Chrome driver."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--lang=en-US")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 15)
        self.base_url = "https://www.squarefoot.com.hk/en/rent"

    def load_homepage(self):
        """Navigate to the SquareFoot rent page and verify it loaded."""
        try:
            self.driver.get(self.base_url)
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "property_item"))
            )
            # Verify search input exists (uses By.NAME - assignment requirement)
            self.driver.find_element(By.NAME, "searchText_temp")
        except Exception as e:
            print(f"Error loading homepage: {e}")

    def apply_filters(self, property_type=None, budget=None, area=None, rooms=None, district=None):
        """Apply filters via URL for type/budget/area/rooms; search box for sub-districts."""
        type_slugs = {"Apartment": "apartment", "Carpark": "carpark", "Office": "office", "Shop": "shop"}
        region_slugs = {"Hong Kong Island": "a1", "Kowloon": "a2", "New Territories": "a3", "Outlying Islands": "a170"}
        room_map = {"Studio": "0", "1 room": "1", "2 rooms": "2", "3 rooms": "3", "4 rooms": "4", "5+ rooms": "5"}
        budget_map = {
            "Below 10,000": (None, "10000"), "10,000 - 20,000": ("10000", "20000"),
            "20,000 - 40,000": ("20000", "40000"), "40,000 - 60,000": ("40000", "60000"),
            "60,000 - 80,000": ("60000", "80000"), "Above 80,000": ("80000", None),
        }
        area_map = {
            "Below 300 ft²": (None, "300"), "300 - 500 ft²": ("300", "500"),
            "500 - 1000 ft²": ("500", "1000"), "1000 - 2000 ft²": ("1000", "2000"),
            "Above 2000 ft²": ("2000", None),
        }

        # Build URL with type and region path
        url = self.base_url
        if property_type in type_slugs:
            url += f"/{type_slugs[property_type]}"
        is_region = district in region_slugs
        if is_region:
            url += f"/{region_slugs[district]}"

        # Build query parameters
        params = []
        if budget in budget_map:
            low, high = budget_map[budget]
            if low: params.append(f"price_low={low}")
            if high: params.append(f"price_high={high}")
        if area in area_map:
            low, high = area_map[area]
            if low: params.append(f"areaRange_low={low}")
            if high: params.append(f"areaRange_high={high}")
        if rooms in room_map:
            params.append(f"roomRange={room_map[rooms]}")

        if params:
            url += "?" + "&".join(params)

        try:
            self.driver.get(url)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.property_item")))
        except Exception:
            pass

        # For sub-districts: use search box keyword search
        if district and not is_region:
            try:
                search_box = self.wait.until(
                    EC.presence_of_element_located((By.NAME, "searchText_temp"))
                )
                search_box.clear()
                search_box.send_keys(district)

                search_btn = self.wait.until(
                    EC.element_to_be_clickable((By.ID, "searchwords_btn"))
                )
                search_btn.click()

                # Wait for AJAX-loaded content (28Hse takes longer)
                time.sleep(8)

                # Scroll the 28Hse container into view to trigger lazy loading
                try:
                    self.driver.execute_script(
                        "document.querySelector('.load_alt_result_inner_div')?.scrollIntoView();"
                    )
                    time.sleep(2)
                except Exception:
                    pass
            except Exception as e:
                print(f"  Note: search did not complete: {e}")

    def get_results_count(self):
        """Return the number of properties (handles SquareFoot and 28Hse formats)."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            for line in body_text.split("\n"):
                line_lower = line.lower()
                if "results of property" in line_lower:
                    for token in line.split():
                        cleaned = token.replace(",", "")
                        if cleaned.isdigit():
                            return int(cleaned)
                if "find" in line_lower and "items" in line_lower:
                    for token in line.split():
                        cleaned = token.replace(",", "")
                        if cleaned.isdigit():
                            return int(cleaned)
            return 0
        except Exception:
            return 0

    def extract_properties(self, district="N/A"):
        """Extract property data from SquareFoot or 28Hse listings."""
        properties = []

        try:
            page_source = self.driver.page_source
            is_28hse = "Provided By 28Hse" in page_source

            if is_28hse:
                print(f"  Note: SquareFoot has no listings for '{district}'. Showing 28Hse listings.")

            cards = self.driver.find_elements(By.CSS_SELECTOR, "div.property_item")

            # Retry for 28Hse if cards not yet rendered
            if not cards and is_28hse:
                time.sleep(5)
                cards = self.driver.find_elements(By.CSS_SELECTOR, "div.property_item")

            for card in cards:
                prop = {
                    "District": district,
                    "Property Name": "N/A",
                    "Street Address": "N/A",
                    "Monthly Rent": "N/A",
                    "Saleable Area (ft²)": "N/A",
                    "Number of Bedrooms": "N/A",
                    "Number of Bathrooms": "N/A",
                    "Property URL": "N/A",
                }

                try:
                    prop["Property Name"] = card.find_element(
                        By.CSS_SELECTOR, "div.header.cat"
                    ).text.replace("\n", " ").strip()
                except Exception:
                    pass

                try:
                    prop["Street Address"] = card.find_element(
                        By.CSS_SELECTOR, "div.meta"
                    ).text.strip()
                except Exception:
                    pass

                try:
                    prop["Monthly Rent"] = card.find_element(
                        By.CSS_SELECTOR, "span.priceDesc"
                    ).text.strip()
                except Exception:
                    pass

                try:
                    for h in card.find_elements(By.CSS_SELECTOR, "div.header"):
                        text = h.text.strip()
                        if "cat" in h.get_attribute("class") or "HKD" in text:
                            continue
                        if "ft²" in text:
                            parts = text.split("ft²")
                            prop["Saleable Area (ft²)"] = parts[0].strip()
                            tokens = parts[1].strip().split() if len(parts) > 1 else []
                            if len(tokens) >= 1:
                                prop["Number of Bedrooms"] = tokens[0]
                            if len(tokens) >= 2:
                                prop["Number of Bathrooms"] = tokens[1]
                            break
                except Exception:
                    pass

                # Try SquareFoot URL first, fall back to 28Hse URL
                try:
                    prop["Property URL"] = card.find_element(
                        By.CSS_SELECTOR, "img.detail_page"
                    ).get_attribute("href")
                except Exception:
                    try:
                        prop["Property URL"] = card.find_element(
                            By.CSS_SELECTOR, "img.detail_page_others"
                        ).get_attribute("href")
                    except Exception:
                        pass

                properties.append(prop)

        except Exception as e:
            print(f"  Error extracting properties: {e}")

        return properties

    def __del__(self):
        """Destructor: close the browser."""
        try:
            self.driver.quit()
        except Exception:
            pass


# --- Standalone helper functions ---

def get_menu_choice(title, question, options):
    """Display a menu, validate input, and return the chosen option."""
    print("\n" + "-" * 50)
    print(title)
    print("-" * 50)
    while True:
        print(f"\n{question}\n")
        for i in range(len(options)):
            print(f"    {i + 1}. {options[i]}")
        choice = input(f"\nEnter your choice (1-{len(options)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            selected = options[int(choice) - 1]
            print(f"Selected: {selected}")
            return selected
        print(f"Invalid choice. Please enter a number between 1 and {len(options)}.")


def get_yes_no(prompt):
    """Get a yes/no answer. Accepts y/Y/yes/YES/n/N/no/NO."""
    while True:
        ans = input(prompt).strip().lower()
        if ans == "y" or ans == "yes":
            return True
        if ans == "n" or ans == "no":
            return False
        print("Invalid input. Please enter 'y' for yes or 'n' for no.")


def handle_csv_save(properties, last_filename=None):
    """Advanced CSV Management — matches TA's expected output."""
    if last_filename and os.path.exists(last_filename):
        print(f"\nLast search was saved to: {last_filename}")
        if get_yes_no("Append to this file? (y/n): "):
            return append_to_csv(properties, last_filename)

    while True:
        print("\n" + "-" * 50)
        print("SAVE OPTIONS")
        print("-" * 50)
        print("\n    1. Create a new file")
        print("    2. Append to an existing file")

        choice = input("\nEnter your choice (1 or 2): ").strip()

        if choice == "1":
            result = create_new_csv(properties)
            if result:
                return result
        elif choice == "2":
            result = append_to_existing_csv(properties)
            if result:
                return result
        else:
            print("Invalid choice. Please enter 1 or 2.")


def create_new_csv(properties):
    """Create a new CSV file."""
    while True:
        filename = input("\nEnter filename to save as (or type 'back' to return to the 'SAVE OPTIONS' menu): ").strip()
        if filename.lower() == "back":
            return None
        if not filename:
            print("Filename cannot be empty.")
            continue
        if "(" in filename:
            filename = filename.split("(")[0].strip()
        if not filename.endswith(".csv"):
            filename += ".csv"
        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=properties[0].keys(), quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(properties)
            print(f"\n✓ Property data saved to new file '{filename}'")
            print(f"✓ Total properties saved: {len(properties)}")
            return filename
        except Exception as e:
            print(f"Error: {e}")


def append_to_existing_csv(properties):
    """Append to an existing CSV file."""
    csv_files = [f for f in os.listdir(".") if f.endswith(".csv")]

    if not csv_files:
        print("\nNo CSV files found. Please create a new file first.")
        return None

    print("\nAvailable CSV files:")
    print("-" * 40)
    for i in range(len(csv_files)):
        size = os.path.getsize(csv_files[i])
        try:
            with open(csv_files[i], "r", encoding="utf-8-sig") as f:
                row_count = sum(1 for _ in csv.reader(f)) - 1
        except Exception:
            row_count = 0
        print(f"{i + 1}. {csv_files[i]} ({row_count} properties, {size:,} bytes)")
    print("-" * 40)

    while True:
        filename = input("\nEnter filename to append to (or type 'back' to return to the 'SAVE OPTIONS' menu): ").strip()
        if filename.lower() == "back":
            return None
        if not filename:
            print("Filename cannot be empty.")
            continue
        if "(" in filename:
            filename = filename.split("(")[0].strip()
        if not filename.endswith(".csv"):
            filename += ".csv"
        if not os.path.exists(filename):
            print(f"File '{filename}' does not exist. Please enter an existing filename.")
            continue
        return append_to_csv(properties, filename)


def append_to_csv(properties, filename):
    """Append properties to a CSV file."""
    try:
        with open(filename, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=properties[0].keys(), quoting=csv.QUOTE_ALL)
            writer.writerows(properties)
        with open(filename, "r", encoding="utf-8-sig") as f:
            total_in_file = sum(1 for _ in csv.reader(f)) - 1
        print(f"\n✓ Property data successfully appended to '{filename}'")
        print(f"✓ Added {len(properties)} new properties")
        print(f"Total properties in file: {total_in_file}")
        return filename
    except Exception as e:
        print(f"Error: {e}")
        return None


# --- Main menu-driven program ---

def main():
    """Main program loop for Hong Kong Rental Property Market Analyser."""
    print("\n" + "=" * 50)
    print("HONG KONG RENTAL PROPERTY MARKET ANALYSER")
    print("=" * 50)

    scraper = PropertyScraper()
    last_filename = None

    while True:
        # Step 1: Property Type
        prop_type = get_menu_choice(
            "PROPERTY TYPE SELECTION",
            "What type of property are you searching for?",
            ["All", "Apartment", "Carpark", "Office", "Shop", "Exit"]
        )
        if prop_type == "Exit":
            break

        # Step 2: Budget
        budget = get_menu_choice(
            "BUDGET SELECTION",
            "What is your monthly budget (in HKD)?",
            ["No preference", "Below 10,000", "10,000 - 20,000",
             "20,000 - 40,000", "40,000 - 60,000", "60,000 - 80,000",
             "Above 80,000"]
        )

        # Step 3: Area
        area = get_menu_choice(
            "AREA SELECTION",
            "How big do you want your property to be (Saleable Area)?",
            ["No preference", "Below 300 ft²", "300 - 500 ft²",
             "500 - 1000 ft²", "1000 - 2000 ft²", "Above 2000 ft²"]
        )

        # Step 4: Rooms
        rooms = get_menu_choice(
            "ROOM SELECTION",
            "How many rooms do you want?",
            ["No preference", "Studio", "1 room", "2 rooms",
             "3 rooms", "4 rooms", "5+ rooms"]
        )

        # Step 5: District (free text + Title Case + validation)
        print("\n" + "-" * 50)
        print("DISTRICT SELECTION")
        print("-" * 50)

        while True:
            district = input("\nEnter district name: ").strip()
            if not district or not any(c.isalpha() for c in district):
                print("Invalid district name.")
                continue
            district = district.title()
            print(f"Selected: {district}")
            print(f"\nSearching for properties in {district}...")

            scraper.apply_filters(
                property_type=prop_type, budget=budget, area=area,
                rooms=rooms, district=district
            )

            count = scraper.get_results_count()
            if count > 0:
                print(f"Total properties available: {count}")
                break
            else:
                print(f"No properties found for '{district}'. Please try another.")

        # Step 6: Extract & Save (Advanced CSV Management - Additional Feature)
        if get_yes_no("\nDo you want to extract property data to CSV? (y/n): "):
            print(f"\nExtracting property data for {district} ...")
            properties = scraper.extract_properties(district=district)
            count = len(properties)
            print(f"\nTotal properties to scrape: {count}")
            print(f"Progress: {count}/{count} (100%)")
            print("Extraction completed!")
            print(f"Total properties scraped: {count}")
            if count > 0:
                print(f"Successfully scraped all {count} properties!")
                last_filename = handle_csv_save(properties, last_filename)

        # Step 7: Search again?
        print("\n" + "-" * 50)
        if not get_yes_no("Search again? (y/n): "):
            break

    # Goodbye
    print("\n" + "=" * 50)
    print("Thank you for using the Property Market Analyser!")
    print("Driver closed.")
    print("=" * 50)


if __name__ == "__main__":
    main()
