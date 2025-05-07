# matr-proto
The circuitpython 9 code to run on a Waveshare RGBMatrix clock. Here's an example settings.toml. You probably only need the PROD url. The DEV url is used automatically when USB is connected to the debug USB port. If you're using the normal power USB port, it'll use PROD

# Comments are supported
CIRCUITPY_WIFI_SSID="SomeSSID"  
CIRCUITPY_WIFI_PASSWORD="some.long.password"  
BIN_URL_DEV="http://192.168.1.2:8080/clock.bin"  
BIN_URL_PROD="http://clock.youdomain.com/clock.bin"  
