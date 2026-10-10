import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class BridgeConfig:
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )
    allowed_users: List[int] = field(default_factory=list)
    
    # MT5 connection options
    mt5_login: Optional[int] = None
    mt5_password: Optional[str] = None
    mt5_server: Optional[str] = None
    mt5_path: Optional[str] = None

    # Trade defaults
    default_lot_size: float = 0.01
    default_deviation: int = 20
    magic_number: int = 100888
    symbol_suffix: str = ""
    auto_detect_suffix: bool = True
    dry_run: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        allowed_users_raw = os.getenv("TELEGRAM_ALLOWED_USERS", "").strip()
        allowed_users = []
        if allowed_users_raw:
            for uid in allowed_users_raw.split(","):
                uid_clean = uid.strip()
                if uid_clean.isdigit():
                    allowed_users.append(int(uid_clean))

        login_raw = os.getenv("MT5_LOGIN", "").strip()
        mt5_login = int(login_raw) if login_raw.isdigit() else None

        password = os.getenv("MT5_PASSWORD", "").strip() or None
        server = os.getenv("MT5_SERVER", "").strip() or None
        path = os.getenv("MT5_PATH", "").strip() or None

        lot_raw = os.getenv("DEFAULT_LOT_SIZE", "0.01").strip()
        try:
            default_lot_size = float(lot_raw)
        except ValueError:
            default_lot_size = 0.01

        dev_raw = os.getenv("DEFAULT_DEVIATION", "20").strip()
        try:
            default_deviation = int(dev_raw)
        except ValueError:
            default_deviation = 20

        magic_raw = os.getenv("MAGIC_NUMBER", "100888").strip()
        try:
            magic_number = int(magic_raw)
        except ValueError:
            magic_number = 100888

        symbol_suffix = os.getenv("SYMBOL_SUFFIX", "").strip()
        auto_detect_suffix = os.getenv("AUTO_DETECT_SUFFIX", "True").strip().lower() in ("true", "1", "yes")
        dry_run = os.getenv("DRY_RUN", "False").strip().lower() in ("true", "1", "yes")
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()

        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            allowed_users=allowed_users,
            mt5_login=mt5_login,
            mt5_password=password,
            mt5_server=server,
            mt5_path=path,
            default_lot_size=default_lot_size,
            default_deviation=default_deviation,
            magic_number=magic_number,
            symbol_suffix=symbol_suffix,
            auto_detect_suffix=auto_detect_suffix,
            dry_run=dry_run,
            log_level=log_level,
        )

    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user_id is allowed to send trade commands."""
        # If allowed_users list is empty, allow all (with warning)
        if not self.allowed_users:
            return True
        return user_id in self.allowed_users
