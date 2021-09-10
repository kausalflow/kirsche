import json
import os
import random

import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


def get_random_user_agent(browsers=None):
    """
    get_random_user_agent returns a random user agent.
    We provide two predefined browers, chrome and firefox.
    :param browsers: which brower to be used, defaults to ["chrome", "firefox"]
    :type browsers: list, optional
    :return: dictionary for requests module to consude as {'User-Agent': "blabla"}
    :rtype: dict
    """

    if browsers is None:
        browsers = ["chrome", "firefox"]
    if isinstance(browsers, str):
        browsers = [browsers]

    chrome_user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36",
        "Mozilla/5.0 (Windows NT 5.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36",
    ]
    firefox_user_agents = [
        "Mozilla/4.0 (compatible; MSIE 9.0; Windows NT 6.1)",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)",
        "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (Windows NT 6.2; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.0; Trident/5.0)",
        "Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0)",
        "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)",
        "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; .NET CLR 2.0.50727; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729)",
    ]

    user_agents_dict = {"chrome": chrome_user_agents, "firefox": firefox_user_agents}

    # error if specified browser is not in the list
    if set(browsers) - set(user_agents_dict.keys()):
        logger.error(f"Unknown browser: {set(browsers) - set(user_agents_dict.keys())}")

    user_agent_list = sum([user_agents_dict[browser] for browser in browsers], [])

    return {"User-Agent": random.choice(user_agent_list)}


def get_session(
    retry_params=None,
    session=None,
):
    """
    get_session prepares a session object.
    :param retry_params: the rules to retry, defaults to {"retries": 5, "backoff_factor": 0.3, "status_forcelist": (500, 502, 504)}
    :type retry_params: dict, optional
    :param session: [description], defaults to None
    :type session: [type], optional
    """

    if retry_params is None:
        retry_params = {
            "retries": 5,
            "backoff_factor": 0.3,
            "status_forcelist": (500, 502, 504),
        }

    if session is None:
        session = requests.Session()

    retry = Retry(
        total=retry_params.get("retries"),
        read=retry_params.get("retries"),
        connect=retry_params.get("retries"),
        backoff_factor=retry_params.get("backoff_factor"),
        status_forcelist=retry_params.get("status_forcelist"),
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def get_session_query_configs(
    headers=None,
    timeout=None,
    proxies=None,
    cookies=None,
):
    """
    get_session_query_configs creates a session config dictionary for session to use. These are the keyword arguments of the session get or post methods.
    Proxies can be set by providing a dictionary of the form
    ```python
    {
        'http': some super_proxy_url,
        'https': some super_proxy_url,
    }
    ```
    :param headers: header of the method such as use agent, defaults to random user agent from get_random_user_agent
    :type headers: dict, optional
    :param timeout: timeout strategy, defaults to (5, 14)
    :type timeout: tuple, optional
    :param proxies: proxy configs, defaults to {}
    :type proxies: dict, optional
    :param cookies: cookie configs, defaults to {"language": "en"}
    :type cookies: dict, optional
    :return: dictionary of session configs for session methods, e.g., get, to use.
    :rtype: dict
    """

    if cookies is None:
        cookies = {"language": "en"}

    if headers is None:
        headers = get_random_user_agent()

    if timeout is None:
        timeout = (5, 14)

    if proxies is None:
        proxies = {}

    return dict(headers=headers, proxies=proxies, cookies=cookies)


def get_page_content(
    link, session=None, session_query_configs=None, method="GET", data=None
):
    """Download page and save content
    :param headers: header information such as useragent, defaults to random user agent from get_random_user_agent
    :type headers: dict, optional
    """

    if not session_query_configs:
        session_query_configs = get_session_query_configs()

    if not session:
        session = get_session(
            retry_params=None,
            session=None,
        )
    if method == "GET":
        content = session.get(link, **session_query_configs)
    elif method == "POST":
        if data is None:
            data = {}
        content = session.post(link, data=data, **session_query_configs)

    status = content.status_code

    return {"status": status, "content": content}


if __name__ == "__main__":

    print(get_random_user_agent())

    print(get_session())

    test_content = get_page_content("https://google.com")
    print(test_content["status"], test_content["content"])

    print(test_content["content"].text)

    pass
