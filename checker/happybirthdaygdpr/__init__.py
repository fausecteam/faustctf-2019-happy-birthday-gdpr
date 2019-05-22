import os

if os.environ.get('GDPR_DONT_IMPORT_CHECKER', None) != 'yes':
    from .checker import HappyBirthdayGdprChecker
