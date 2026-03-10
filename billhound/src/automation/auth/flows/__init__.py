"""
Auth flow strategies.
Importing this package triggers registration of all concrete auth strategies.
"""
from src.automation.auth.flows.adobe_auth import AdobeAuthStrategy  # noqa: F401
from src.automation.auth.flows.amazon_prime_auth import AmazonPrimeAuthStrategy  # noqa: F401
from src.automation.auth.flows.canva_auth import CanvaAuthStrategy  # noqa: F401
from src.automation.auth.flows.disney_plus_auth import DisneyPlusAuthStrategy  # noqa: F401
from src.automation.auth.flows.hulu_auth import HuluAuthStrategy  # noqa: F401
from src.automation.auth.flows.microsoft365_auth import Microsoft365AuthStrategy  # noqa: F401
from src.automation.auth.flows.netflix_auth import NetflixAuthStrategy  # noqa: F401
from src.automation.auth.flows.nordvpn_auth import NordvpnAuthStrategy  # noqa: F401
from src.automation.auth.flows.spotify_auth import SpotifyAuthStrategy  # noqa: F401
from src.automation.auth.flows.youtube_premium_auth import YoutubePremiumAuthStrategy  # noqa: F401
