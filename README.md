# matr-proto
The circuitpython 9 code to run on a Waveshare RGBMatrix clock. You probably only need the PROD url. The DEV url is used automatically when USB is connected to the debug USB port. If you're using the normal power USB port, it'll use PROD

# example settings.toml
CIRCUITPY_WIFI_SSID="SomeSSID"  
CIRCUITPY_WIFI_PASSWORD="some.long.password"  
BIN_URL_DEV="http://192.168.1.2:8080/clock.bin"  
BIN_URL_PROD="http://clock.youdomain.com/clock.bin"  

You'll note there's a gif.py in here. That can decode gifs, but it's slow, like 4FPS slow. The bin.py decoder runs at around 16FPS. Hence, bins. I can't remember if they use the same interfaces. Probably not.
