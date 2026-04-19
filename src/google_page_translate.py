# -*- coding: utf-8 -*-
"""
Google Translate API using translate-pa.googleapis.com/v1/translateHtml
Based on the working implementation from trans.google_page.js
"""

import time
import logging
import requests
from my_log import log_print

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520"
GOOGLE_TARGET_URL = "https://translate-pa.googleapis.com/v1/translateHtml"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"


class GooglePageTranslate:
    """
    Google Translate using the public API endpoint (translate-pa.googleapis.com)
    Same approach as the working trans.google_page.js implementation
    """

    def __init__(self, target_url=None, proxies=None):
        self.target_url = target_url or GOOGLE_TARGET_URL
        self.proxies = proxies
        self.session = requests.Session()
        self.is_translating = False

        user_agent = DEFAULT_USER_AGENT
        if proxies:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        self.session.headers.update(
            {
                "Content-Type": "application/json+protobuf",
                "User-Agent": user_agent,
                "Referer": "https://translate.google.com/",
                "x-goog-api-key": GOOGLE_API_KEY,
            }
        )

    def translate(self, texts, target=None, source=None, fmt="text"):
        """
        Translate a list of texts.

        :param texts: List of strings to translate
        :param target: Target language code (e.g., 'zh-CN', 'ja')
        :param source: Source language code (e.g., 'en', 'ja')
        :param fmt: Format type ('text' or 'html')
        :return: List of TranslateResponse objects
        """
        if not texts:
            return []

        if self.is_translating:
            log_print("GooglePageTranslate: already translating, skipping")
            return []

        results = []
        batch_size = 50

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                batch_results = self._translate_batch(batch, target, source)
                results.extend(batch_results)
            except Exception as e:
                log_print(f"GooglePageTranslate: batch translation error: {e}")
                for text in batch:
                    results.append(TranslateResponse(text, text))
                time.sleep(1)

        return results

    def _translate_batch(self, texts, target, source):
        """Translate a batch of texts using the Google API."""
        self.is_translating = True

        try:
            # Replace newlines with <brk> tag (same as JS implementation)
            filtered_texts = [text.replace("\n", "<brk>") for text in texts]

            # Data format must match JS implementation exactly:
            # [[texts, sourceLang, targetLang], "te_lib"]
            data = [[filtered_texts, source or "auto", target or "en"], "te_lib"]

            response = self.session.post(
                self.target_url,
                json=data,
                proxies=self.proxies,
                timeout=30,
            )

            if response.status_code != 200:
                log_print(
                    f"GooglePageTranslate: API error status={response.status_code}"
                )
                return [TranslateResponse(t, t) for t in texts]

            resp_data = response.json()
            translations = []

            if isinstance(resp_data, (list, dict)):
                # Handle different response formats
                translated_texts = self._parse_response(resp_data, texts)
            else:
                translated_texts = [resp_data]

            for i, orig in enumerate(texts):
                if i < len(translated_texts):
                    translated = translated_texts[i]
                    # Restore newlines from <brk> tags
                    translated = translated.replace("<brk>", "\n")
                    translated = translated.replace("<brk/>", "\n")
                    translated = translated.replace("<brk />", "\n")
                    # Decode HTML entities
                    translated = translated.replace("&amp;", "&")
                    translated = translated.replace("&lt;", "<")
                    translated = translated.replace("&gt;", ">")
                    translated = translated.replace("&quot;", '"')
                    translated = translated.replace("&#39;", "'")
                    translated = translated.replace("&apos;", "'")
                else:
                    translated = orig
                translations.append(TranslateResponse(orig, translated))

            return translations

        except Exception as e:
            log_print(f"GooglePageTranslate: error in _translate_batch: {e}")
            return [TranslateResponse(t, t) for t in texts]
        finally:
            self.is_translating = False

    def _parse_response(self, resp_data, original_texts):
        """Parse the JSON response from Google API."""
        translations = []

        try:
            # Try to extract translated text from response
            # The response format from translate-pa.googleapis.com/v1/translateHtml
            # can vary. We handle common patterns.

            if isinstance(resp_data, dict):
                # Response might have 'translations' key
                if "translations" in resp_data:
                    for item in resp_data["translations"]:
                        if isinstance(item, dict):
                            translations.append(item.get("translatedText", ""))
                        elif isinstance(item, (list, tuple)) and len(item) > 0:
                            translations.append(str(item[0]))
                # Response might have 'data' key
                elif "data" in resp_data:
                    data = resp_data["data"]
                    if isinstance(data, dict) and "translations" in data:
                        for item in data["translations"]:
                            if isinstance(item, dict):
                                translations.append(item.get("translatedText", ""))
                            elif isinstance(item, (list, tuple)) and len(item) > 0:
                                translations.append(str(item[0]))
                    elif isinstance(data, (list, tuple)):
                        for item in data:
                            if isinstance(item, dict):
                                translations.append(item.get("translatedText", ""))
                            elif isinstance(item, (list, tuple)):
                                if len(item) > 0:
                                    translations.append(str(item[0]))
                                else:
                                    translations.append("")
                            else:
                                translations.append(str(item))
                else:
                    # Try to find any list in the response
                    for key, value in resp_data.items():
                        if isinstance(value, list):
                            for item in value:
                                if isinstance(item, (list, tuple)):
                                    if len(item) > 0:
                                        translations.append(str(item[0]))
                                    else:
                                        translations.append("")
                                elif isinstance(item, dict):
                                    translations.append(
                                        item.get("translatedText", str(item))
                                    )
                                else:
                                    translations.append(str(item))
                            break
            elif isinstance(resp_data, list):
                # Response is a list
                if len(resp_data) > 0:
                    first_item = resp_data[0]
                    if isinstance(first_item, list):
                        # Nested list format (like the old Google Translate API)
                        for item in first_item:
                            if isinstance(item, (list, tuple)) and len(item) > 0:
                                translations.append(str(item[0]))
                            elif isinstance(item, dict):
                                translations.append(item.get("translatedText", ""))
                            else:
                                translations.append(str(item))
                    else:
                        for item in resp_data:
                            if isinstance(item, dict):
                                translations.append(item.get("translatedText", ""))
                            elif isinstance(item, (list, tuple)) and len(item) > 0:
                                translations.append(str(item[0]))
                            else:
                                translations.append(str(item))
                else:
                    translations = [""] * len(original_texts)
        except Exception as e:
            log_print(f"GooglePageTranslate: error parsing response: {e}")
            translations = [""] * len(original_texts)

        # Ensure we have the right number of translations
        while len(translations) < len(original_texts):
            translations.append("")

        return translations[: len(original_texts)]


class TranslateResponse:
    """Simple class to hold translation result."""

    def __init__(self, untranslatedText, translatedText):
        self.untranslatedText = untranslatedText
        self.translatedText = translatedText
