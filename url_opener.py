import os


class UrlOpener:
    def open_url(self, url):
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            os.startfile(url)
        except Exception as e:
            print("Error opening URL:", e)
