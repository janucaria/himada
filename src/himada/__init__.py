from importlib.metadata import version, PackageNotFoundError

APP_NAME = "Himada"

try:
    APP_VERSION = version("himada")
except PackageNotFoundError:
    APP_VERSION = "dev"
