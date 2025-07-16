import logging
import xml.etree.ElementTree as ET


def parse_device_account_from_xml(xml_path: str):
    """Parse device account and password from XML file."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        account = None
        password = None
        
        for string_tag in root.findall('string'):
            name_attr = string_tag.get('name')
            if name_attr == 'deviceAccount':
                account = string_tag.text
                logging.info("Found deviceAccount in XML: %s", account)
            elif name_attr == 'devicePassword':
                password = string_tag.text
                logging.info("Found devicePassword in XML: %s", password)
        
        return account, password
        
    except (ET.ParseError, FileNotFoundError) as e:
        logging.warning("Could not parse XML file %s: %s", xml_path, e)
        return None, None