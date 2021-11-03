from dataclasses import dataclass, field


@dataclass
class App:
    google_maps_api_key: str = 'FSPJYsNILCTwkFy8xt6fUUNQqLVjK5K8Cqt7l4S'
    sleep_minutes: int = 15
    chrome_profile_path: str = '/tmp/ChromeUserData'
    debug: bool = False


@dataclass
class Info:
    full_name: str = 'John Doe'
    nie: str = 'Y1234567X'
    country_code: int = 257
    email: str = 'john.doe@example.com'
    phone: str = '657666666'
    current_expiry_date: str = '09/06/2021'
    address: str = 'Passeig de Sant Joan, 189'
    offices_distances: dict = field(default_factory=dict)
    tramite_code: int = 4010
    max_cita_date: str = '06/09/2021'
