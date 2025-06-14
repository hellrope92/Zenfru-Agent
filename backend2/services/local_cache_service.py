"""
Local Cache Service for storing and retrieving Kolla API data
Handles caching of schedules, appointments, and contacts with time-based refresh
"""

import json
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

class LocalCacheService:
    def __init__(self, db_path: str = "cache.db"):
        """Initialize the local cache service"""
        self.db_path = Path(__file__).parent.parent / db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Schedules table (refresh every 8 hours)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                data TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Appointments table (refresh every 24 hours)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id TEXT UNIQUE,
                patient_name TEXT,
                patient_dob TEXT,
                patient_phone TEXT,
                data TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add patient_phone column if it doesn't exist (migration for existing databases)
        try:
            cursor.execute('ALTER TABLE appointments ADD COLUMN patient_phone TEXT')
            print("Added patient_phone column to appointments table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                # Column already exists, which is fine
                pass
            else:
                print(f"Error adding patient_phone column: {e}")
        
        # Contacts table (refresh every 24 hours)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT UNIQUE,
                patient_name TEXT,
                patient_dob TEXT,
                patient_phone TEXT,
                data TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add patient_phone column to contacts table if it doesn't exist
        try:
            cursor.execute('ALTER TABLE contacts ADD COLUMN patient_phone TEXT')
            print("Added patient_phone column to contacts table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                # Column already exists, which is fine
                pass
            else:
                print(f"Error adding patient_phone column to contacts: {e}")
        
        # Cache metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_metadata (
                key TEXT PRIMARY KEY,
                last_full_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def is_cache_stale(self, table: str, hours: int = 24) -> bool:
        """Check if cache is stale based on time threshold"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f'''
            SELECT last_updated FROM {table} 
            ORDER BY last_updated DESC LIMIT 1
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True
        
        last_updated = datetime.fromisoformat(result[0])
        return datetime.now() - last_updated > timedelta(hours=hours)
    
    def store_schedule(self, date: str, data: Dict[str, Any]):
        """Store schedule data for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO schedules (date, data, last_updated)
            VALUES (?, ?, ?)        ''', (date, json.dumps(data), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_schedule(self, date: str) -> Optional[Dict[str, Any]]:
        """Get schedule data for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT data, last_updated FROM schedules 
            WHERE date = ?
        ''', (date,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # Check if data is still fresh (24 hours for schedules)
            last_updated = datetime.fromisoformat(result[1])
            if datetime.now() - last_updated < timedelta(hours=24):
                return json.loads(result[0])
        
        return None
    
    def store_appointment(self, appointment_data: Dict[str, Any]):
        """Store appointment data using existing schema fields"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract relevant fields from appointment data
        appointment_id = appointment_data.get("id", "")
        
        # Try to get patient name from contact information
        contact = appointment_data.get("contact", {})
        given_name = contact.get("given_name", "")
        family_name = contact.get("family_name", "")
        contact_name = contact.get("name", "")
        
        if contact_name:
            patient_name = contact_name
        elif given_name and family_name:
            patient_name = f"{given_name} {family_name}"
        elif given_name:
            patient_name = given_name
        else:
            patient_name = ""
            
        patient_dob = contact.get("birth_date", "")
        
        cursor.execute('''
            INSERT OR REPLACE INTO appointments (appointment_id, patient_name, patient_dob, data, last_updated)
            VALUES (?, ?, ?, ?, ?)
        ''', (appointment_id, patient_name, patient_dob, json.dumps(appointment_data), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_appointments_by_patient(self, patient_name: str, patient_dob: str) -> List[Dict[str, Any]]:
        """Get appointments for a specific patient"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT data, last_updated FROM appointments 
            WHERE LOWER(patient_name) = LOWER(?) AND patient_dob = ?
        ''', (patient_name, patient_dob))
        
        results = cursor.fetchall()
        conn.close()
        
        appointments = []
        for result in results:
            # Check if data is still fresh (24 hours)
            last_updated = datetime.fromisoformat(result[1])
            if datetime.now() - last_updated < timedelta(hours=24):
                appointments.append(json.loads(result[0]))
        
        return appointments
    
    def get_appointments_by_phone(self, patient_phone: str) -> List[Dict[str, Any]]:
        """Get appointments for a specific patient by phone number by checking contact primary_phone_number"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all appointments and check their contact data for matching phone numbers
        cursor.execute('''
            SELECT data, last_updated FROM appointments
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        matching_appointments = []
        for result in results:
            # Check if data is still fresh (24 hours)
            last_updated = datetime.fromisoformat(result[1])
            if datetime.now() - last_updated < timedelta(hours=24):
                appointment_data = json.loads(result[0])
                
                # Check if this appointment's contact has the matching phone number
                contact = appointment_data.get("contact", {})
                primary_phone = contact.get("primary_phone_number", "")
                
                # Normalize both phone numbers for comparison
                normalized_primary = primary_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                normalized_search = patient_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                
                if normalized_primary == normalized_search:
                    matching_appointments.append(appointment_data)
        
        return matching_appointments
    
    def store_contact(self, contact_id: str, patient_name: str, patient_dob: str, data: Dict[str, Any]):
        """Store contact data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO contacts (contact_id, patient_name, patient_dob, data, last_updated)
            VALUES (?, ?, ?, ?, ?)
        ''', (contact_id, patient_name, patient_dob, json.dumps(data), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_contact_by_patient(self, patient_name: str, patient_dob: str) -> Optional[Dict[str, Any]]:
        """Get contact data for a specific patient"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT data, last_updated FROM contacts 
            WHERE LOWER(patient_name) = LOWER(?) AND patient_dob = ?
            ORDER BY last_updated DESC LIMIT 1
        ''', (patient_name, patient_dob))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # Check if data is still fresh (24 hours)
            last_updated = datetime.fromisoformat(result[1])
            if datetime.now() - last_updated < timedelta(hours=24):
                return json.loads(result[0])
        
        return None
    
    def cleanup_old_data(self):
        """Clean up old cache data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Remove schedules older than 24 hours
        cutoff_schedules = (datetime.now() - timedelta(hours=24)).isoformat()
        cursor.execute('DELETE FROM schedules WHERE last_updated < ?', (cutoff_schedules,))
        
        # Remove appointments and contacts older than 48 hours
        cutoff_data = (datetime.now() - timedelta(hours=48)).isoformat()
        cursor.execute('DELETE FROM appointments WHERE last_updated < ?', (cutoff_data,))
        cursor.execute('DELETE FROM contacts WHERE last_updated < ?', (cutoff_data,))
        
        conn.commit()
        conn.close()
    
    def get_all_schedules(self, days: int = 3) -> Dict[str, Any]:
        """Get all schedules for the next N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        schedules = {}
        today = datetime.now()
        
        for i in range(days):
            date = (today + timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT data, last_updated FROM schedules 
                WHERE date = ?
            ''', (date,))
            
            result = cursor.fetchone()
            if result:
                last_updated = datetime.fromisoformat(result[1])
                if datetime.now() - last_updated < timedelta(hours=24):
                    schedules[date] = json.loads(result[0])
        
        conn.close()
        return schedules
    
    def get_appointment_by_id(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific appointment by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT data, last_updated FROM appointments 
            WHERE appointment_id = ?
        ''', (appointment_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # Check if data is still fresh (24 hours)
            last_updated = datetime.fromisoformat(result[1])
            if datetime.now() - last_updated < timedelta(hours=24):
                return json.loads(result[0])
        
        return None

    def get_all_appointments(self) -> List[Dict[str, Any]]:
        """Get all cached appointments that are still fresh"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT data, last_updated FROM appointments 
            ORDER BY last_updated DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        appointments = []
        for result in results:
            # Check if data is still fresh (24 hours)
            last_updated = datetime.fromisoformat(result[1])
            if datetime.now() - last_updated < timedelta(hours=24):
                appointments.append(json.loads(result[0]))
        
        return appointments
