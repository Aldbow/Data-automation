"""
ISB LKPP to Google Sheets Integration System
Template untuk otomasi pengambilan data dari ISB LKPP dan update ke Google Sheets secara real-time

Author: [Your Name]
Created: October 2025
"""

import requests
import time
import json
import logging
import schedule
from datetime import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('isb_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ISBLKPPIntegration:
    """
    Kelas utama untuk integrasi ISB LKPP dengan Google Sheets
    """

    def __init__(self, config_file='config.json'):
        """
        Inisialisasi dengan konfigurasi dari file JSON

        Args:
            config_file (str): Path ke file konfigurasi JSON
        """
        self.config = self.load_config(config_file)
        self.session = requests.Session()
        self.driver = None
        self.sheets_client = None
        self.spreadsheet = None
        self.last_update = None

    def load_config(self, config_file):
        """
        Load konfigurasi dari file JSON

        Args:
            config_file (str): Path ke file konfigurasi

        Returns:
            dict: Dictionary konfigurasi
        """
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Konfigurasi berhasil dimuat dari {config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"File konfigurasi {config_file} tidak ditemukan")
            # Return default config template
            return self.create_default_config()
        except json.JSONDecodeError:
            logger.error(f"Format JSON tidak valid dalam {config_file}")
            return {}

    def create_default_config(self):
        """
        Buat template konfigurasi default

        Returns:
            dict: Template konfigurasi default
        """
        default_config = {
            "isb_credentials": {
                "username": "your_isb_username",
                "password": "your_isb_password",
                "login_url": "https://isb.lkpp.go.id/isb-2/login",
                "api_base_url": "https://isb.lkpp.go.id/isb-2/api"
            },
            "google_sheets": {
                "credentials_file": "path/to/service-account-key.json",
                "spreadsheet_id": "your_google_sheets_id",
                "worksheet_name": "Sheet1"
            },
            "automation": {
                "update_interval_minutes": 30,
                "max_retries": 3,
                "timeout_seconds": 30
            },
            "api_endpoints": {
                "ecat_penyedia": "/b2231dd9-cf41-43cb-8a1a-26922abec2e3/json/1814/Ecat-PenyediaDetail/tipe/4/parameter/",
                "ecat_paket": "/b2231dd9-cf41-43cb-8a1a-26922abec2e3/json/1814/Ecat-PaketEPurchasing/",
                "tender_data": "/b2231dd9-cf41-43cb-8a1a-26922abec2e3/json/1814/Bela-TokoDaringRealisasi/"
            }
        }

        # Save default config
        with open('config_template.json', 'w') as f:
            json.dump(default_config, f, indent=4)
        logger.info("Template konfigurasi default telah dibuat: config_template.json")

        return default_config

    def setup_selenium_driver(self):
        """
        Setup Selenium WebDriver untuk otomasi browser
        """
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')  # Run in background
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')

            self.driver = webdriver.Chrome(options=options)
            logger.info("Selenium WebDriver berhasil diinisialisasi")
            return True
        except Exception as e:
            logger.error(f"Gagal menginisialisasi WebDriver: {str(e)}")
            return False

    def login_to_isb(self):
        """
        Login ke sistem ISB LKPP menggunakan Selenium

        Returns:
            bool: True jika login berhasil, False jika gagal
        """
        try:
            if not self.driver:
                if not self.setup_selenium_driver():
                    return False

            logger.info("Memulai proses login ke ISB LKPP")

            # Navigate to login page
            login_url = self.config['isb_credentials']['login_url']
            self.driver.get(login_url)

            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )

            # Fill login form
            username_field = self.driver.find_element(By.NAME, "username")
            password_field = self.driver.find_element(By.NAME, "password")

            username_field.clear()
            username_field.send_keys(self.config['isb_credentials']['username'])

            password_field.clear()
            password_field.send_keys(self.config['isb_credentials']['password'])

            # Submit login form
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()

            # Wait for successful login (check for dashboard or success indicator)
            WebDriverWait(self.driver, 10).until(
                lambda driver: "dashboard" in driver.current_url.lower() or 
                               "beranda" in driver.current_url.lower()
            )

            # Get cookies for requests session
            selenium_cookies = self.driver.get_cookies()
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])

            logger.info("Login ke ISB LKPP berhasil")
            return True

        except TimeoutException:
            logger.error("Timeout saat mencoba login ke ISB LKPP")
            return False
        except Exception as e:
            logger.error(f"Error saat login ke ISB LKPP: {str(e)}")
            return False

    def setup_google_sheets(self):
        """
        Setup koneksi ke Google Sheets API

        Returns:
            bool: True jika setup berhasil, False jika gagal
        """
        try:
            # Define the scope
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]

            # Load credentials
            credentials_path = self.config['google_sheets']['credentials_file']
            creds = Credentials.from_service_account_file(credentials_path, scopes=scope)

            # Create client
            self.sheets_client = gspread.authorize(creds)

            # Open spreadsheet
            spreadsheet_id = self.config['google_sheets']['spreadsheet_id']
            self.spreadsheet = self.sheets_client.open_by_key(spreadsheet_id)

            logger.info("Koneksi ke Google Sheets berhasil")
            return True

        except Exception as e:
            logger.error(f"Gagal setup Google Sheets: {str(e)}")
            return False

    def fetch_data_from_api(self, endpoint_key, params=None):
        """
        Ambil data dari API ISB LKPP

        Args:
            endpoint_key (str): Key endpoint di konfigurasi
            params (dict): Parameter tambahan untuk API call

        Returns:
            dict: Data response dari API atau None jika gagal
        """
        try:
            endpoint = self.config['api_endpoints'].get(endpoint_key)
            if not endpoint:
                logger.error(f"Endpoint {endpoint_key} tidak ditemukan dalam konfigurasi")
                return None

            api_url = self.config['isb_credentials']['api_base_url'] + endpoint

            if params:
                api_url += "/".join(str(v) for v in params.values())

            logger.info(f"Mengambil data dari: {api_url}")

            response = self.session.get(
                api_url,
                timeout=self.config['automation']['timeout_seconds']
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"Berhasil mengambil {len(data) if isinstance(data, list) else 1} record")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error saat mengambil data dari API: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            return None

    def process_data(self, raw_data, data_type):
        """
        Proses dan transformasi data sesuai kebutuhan

        Args:
            raw_data (dict/list): Data mentah dari API
            data_type (str): Tipe data untuk menentukan pemrosesan

        Returns:
            pd.DataFrame: Data yang sudah diproses
        """
        try:
            if not raw_data:
                return pd.DataFrame()

            # Convert to DataFrame
            if isinstance(raw_data, list):
                df = pd.DataFrame(raw_data)
            elif isinstance(raw_data, dict):
                # Handle nested data structures
                if 'data' in raw_data:
                    df = pd.DataFrame(raw_data['data'])
                else:
                    df = pd.DataFrame([raw_data])
            else:
                logger.warning("Format data tidak dikenali")
                return pd.DataFrame()

            # Data cleaning and transformation
            df = self.clean_dataframe(df, data_type)

            # Add metadata
            df['last_updated'] = datetime.now().isoformat()
            df['data_source'] = f'ISB_LKPP_{data_type}'

            logger.info(f"Data berhasil diproses: {len(df)} rows, {len(df.columns)} columns")
            return df

        except Exception as e:
            logger.error(f"Error saat memproses data: {str(e)}")
            return pd.DataFrame()

    def clean_dataframe(self, df, data_type):
        """
        Bersihkan dan standardisasi DataFrame

        Args:
            df (pd.DataFrame): DataFrame yang akan dibersihkan
            data_type (str): Tipe data untuk menentukan pembersihan yang spesifik

        Returns:
            pd.DataFrame: DataFrame yang sudah dibersihkan
        """
        # Remove duplicate rows
        df = df.drop_duplicates()

        # Handle missing values
        df = df.fillna('')

        # Standardize column names
        df.columns = [col.replace(' ', '_').lower() for col in df.columns]

        # Type-specific cleaning
        if data_type == 'ecat_penyedia':
            # Specific cleaning for provider data
            if 'nama_penyedia' in df.columns:
                df['nama_penyedia'] = df['nama_penyedia'].str.strip()

        elif data_type == 'ecat_paket':
            # Specific cleaning for package data
            if 'harga' in df.columns:
                df['harga'] = pd.to_numeric(df['harga'], errors='coerce')

        return df

    def update_google_sheets(self, dataframe, worksheet_name=None):
        """
        Update data ke Google Sheets

        Args:
            dataframe (pd.DataFrame): Data yang akan diupdate
            worksheet_name (str): Nama worksheet, default dari config

        Returns:
            bool: True jika update berhasil, False jika gagal
        """
        try:
            if dataframe.empty:
                logger.warning("DataFrame kosong, tidak ada data untuk diupdate")
                return False

            if not worksheet_name:
                worksheet_name = self.config['google_sheets']['worksheet_name']

            # Get or create worksheet
            try:
                worksheet = self.spreadsheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                worksheet = self.spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="20")
                logger.info(f"Worksheet '{worksheet_name}' dibuat")

            # Clear existing data (keep headers)
            worksheet.clear()

            # Convert DataFrame to list of lists for gspread
            data_to_update = [dataframe.columns.tolist()] + dataframe.values.tolist()

            # Update worksheet
            worksheet.update('A1', data_to_update)

            logger.info(f"Berhasil update {len(dataframe)} rows ke worksheet '{worksheet_name}'")
            return True

        except Exception as e:
            logger.error(f"Error saat update Google Sheets: {str(e)}")
            return False

    def check_for_changes(self, current_data, data_type):
        """
        Cek apakah ada perubahan data dibanding update terakhir

        Args:
            current_data (pd.DataFrame): Data saat ini
            data_type (str): Tipe data untuk caching

        Returns:
            bool: True jika ada perubahan, False jika tidak ada
        """
        try:
            cache_file = f'cache_{data_type}.pkl'

            try:
                last_data = pd.read_pickle(cache_file)

                # Compare data
                if current_data.equals(last_data):
                    logger.info(f"Tidak ada perubahan pada data {data_type}")
                    return False
                else:
                    logger.info(f"Terdeteksi perubahan pada data {data_type}")
                    # Save current data to cache
                    current_data.to_pickle(cache_file)
                    return True

            except FileNotFoundError:
                logger.info(f"Cache file untuk {data_type} tidak ditemukan, membuat yang baru")
                current_data.to_pickle(cache_file)
                return True

        except Exception as e:
            logger.error(f"Error saat cek perubahan data: {str(e)}")
            return True  # Assume there are changes if we can't check

    def run_single_update(self):
        """
        Jalankan satu siklus update data

        Returns:
            bool: True jika update berhasil, False jika gagal
        """
        logger.info("Memulai siklus update data")

        # Ensure we're logged in
        if not self.login_to_isb():
            logger.error("Gagal login, update dibatalkan")
            return False

        # Ensure Google Sheets is setup
        if not self.sheets_client and not self.setup_google_sheets():
            logger.error("Gagal setup Google Sheets, update dibatalkan")
            return False

        success_count = 0
        total_endpoints = len(self.config['api_endpoints'])

        # Process each endpoint
        for endpoint_key in self.config['api_endpoints'].keys():
            try:
                logger.info(f"Memproses endpoint: {endpoint_key}")

                # Fetch data
                raw_data = self.fetch_data_from_api(endpoint_key)
                if not raw_data:
                    continue

                # Process data
                processed_data = self.process_data(raw_data, endpoint_key)
                if processed_data.empty:
                    continue

                # Check for changes
                if not self.check_for_changes(processed_data, endpoint_key):
                    continue

                # Update Google Sheets
                worksheet_name = f"{endpoint_key}_{datetime.now().strftime('%Y%m%d')}"
                if self.update_google_sheets(processed_data, worksheet_name):
                    success_count += 1

            except Exception as e:
                logger.error(f"Error saat memproses endpoint {endpoint_key}: {str(e)}")
                continue

        self.last_update = datetime.now()
        logger.info(f"Update selesai: {success_count}/{total_endpoints} endpoint berhasil")

        return success_count > 0

    def start_scheduled_updates(self):
        """
        Mulai jadwal update otomatis
        """
        interval = self.config['automation']['update_interval_minutes']
        logger.info(f"Memulai jadwal update setiap {interval} menit")

        # Schedule the job
        schedule.every(interval).minutes.do(self.run_single_update)

        # Run immediately on start
        self.run_single_update()

        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def cleanup(self):
        """
        Bersihkan resources
        """
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver ditutup")

        if self.session:
            self.session.close()
            logger.info("Session ditutup")

def main():
    """
    Fungsi utama untuk menjalankan sistem integrasi
    """
    try:
        # Initialize integration system
        integration = ISBLKPPIntegration()

        # Start scheduled updates
        integration.start_scheduled_updates()

    except KeyboardInterrupt:
        logger.info("Program dihentikan oleh user")
    except Exception as e:
        logger.error(f"Error dalam program utama: {str(e)}")
    finally:
        if 'integration' in locals():
            integration.cleanup()

if __name__ == "__main__":
    main()
