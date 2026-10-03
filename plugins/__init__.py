from pkgutil import extend_path


# Keep Django's test discovery while allowing separately installed plugin wheels.
__path__ = extend_path(__path__, __name__)
