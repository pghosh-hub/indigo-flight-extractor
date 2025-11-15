
import pytesseract
from PIL import Image
import re
import csv
import argparse

def extract_text_from_image(image_path):
    """Extracts text from an image file."""
    try:
        text = pytesseract.image_to_string(Image.open(image_path))
        # Fix common OCR errors
        text = text.replace('Olh', '01h').replace('(12)', '(T2)')
        return text
    except Exception as e:
        return str(e)

def parse_flight_details(text):
    """Parses the extracted text to get flight details."""
    flights = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Start of a new flight segment
        if re.match(r'[A-Z]{3}-[A-Z]{3}\s*#', line):
            flight = {}

            # Flight number
            flight_no_match = re.search(r'#\s*(.*)', line)
            if flight_no_match:
                flight['flight_no'] = flight_no_match.group(1).strip()

            i += 1
            # Next line should be "Operated by..."
            if i < len(lines) and "Operated by" in lines[i]:
                flight['carrier'] = lines[i].replace("Operated by ", "").strip()
                i += 1

            # Next line should be times
            if i < len(lines) and re.match(r'\d{2}:\d{2}\s+\d{2}:\d{2}', lines[i]):
                times = re.findall(r'(\d{2}:\d{2})', lines[i])
                flight['departure'] = times[0]
                flight['arrival'] = times[1]
                i += 1

            # Next line is duration
            if i < len(lines) and re.match(r'\d{2}h\s+\d{2}m', lines[i]):
                flight['duration'] = lines[i].split('.')[0]
                i += 1

            # Next line is locations
            if i < len(lines):
                location_line = lines[i]
                if '(' in location_line:
                    locations = re.findall(r'([A-Z\s]+?)\s*\(.*?\)', location_line)
                    if len(locations) >= 2:
                        flight['from'] = locations[0].strip()
                        flight['to'] = locations[1].strip()
                else:
                    parts = location_line.split()
                    if len(parts) >= 2:
                        flight['from'] = parts[0]
                        flight['to'] = parts[1]
                i += 1

            if all(k in flight for k in ['carrier', 'flight_no', 'from', 'to', 'departure', 'arrival', 'duration']):
                flights.append(flight)

        elif "layover" in line:
            layover_match = re.search(r'(\d{2}h\s+\d{2}m)\s+layover', line)
            if layover_match and flights:
                flights[-1]['layover'] = layover_match.group(1)
            i += 1

        else:
            i += 1

    return flights

def write_to_csv(flights, filename="flight_details.csv"):
    """Writes the flight details to a CSV file."""
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['Carrier', 'Flight No.', 'From', 'To', 'Departure', 'Arrival', 'Duration', 'Layover Time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for flight in flights:
            writer.writerow({
                'Carrier': flight.get('carrier'),
                'Flight No.': flight.get('flight_no'),
                'From': flight.get('from'),
                'To': flight.get('to'),
                'Departure': flight.get('departure'),
                'Arrival': flight.get('arrival'),
                'Duration': flight.get('duration'),
                'Layover Time': flight.get('layover', '')
            })

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract flight details from an image.')
    parser.add_argument('image_path', type=str, help='The path to the image file.')
    args = parser.parse_args()

    extracted_text = extract_text_from_image(args.image_path)
    flight_details = parse_flight_details(extracted_text)
    write_to_csv(flight_details)
    print(f"Flight details saved to flight_details.csv")
