import rtc
from adafruit_datetime import datetime
from lib.utils import get_url, make_requests_session, cleanup_session

# Function to grab clock.json, parse JSON, and set the RTC using the ISO8601 timestamp in the time field
def set_rtc():
    url = get_url()
    try:
        session = make_requests_session()

        response = session.get(url + "/clock.json")
        data = response.json()
        time_str = data["time"]
        print("Setting RTC to:", time_str)
        rtc.RTC().datetime = datetime.fromisoformat(time_str).timetuple()

    except Exception as e:
        print("Error setting RTC:", e)
    finally:
        cleanup_session(response, session)