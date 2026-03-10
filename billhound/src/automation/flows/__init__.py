"""
Cancellation flow strategies.
Importing this package triggers registration of all concrete strategies.
"""
from src.automation.flows.adobe import AdobeStrategy  # noqa: F401
from src.automation.flows.amazon_prime import AmazonPrimeStrategy  # noqa: F401
from src.automation.flows.canva import CanvaStrategy  # noqa: F401
from src.automation.flows.disney_plus import DisneyPlusStrategy  # noqa: F401
from src.automation.flows.hulu import HuluStrategy  # noqa: F401
from src.automation.flows.microsoft365 import Microsoft365Strategy  # noqa: F401
from src.automation.flows.netflix import NetflixStrategy  # noqa: F401
from src.automation.flows.nordvpn import NordvpnStrategy  # noqa: F401
from src.automation.flows.spotify import SpotifyStrategy  # noqa: F401
from src.automation.flows.youtube_premium import YoutubePremiumStrategy  # noqa: F401
