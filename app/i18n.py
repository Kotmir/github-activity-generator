"""Server-side messages (RU / EN). The UI has its own dictionary in
assets/js/i18n.js; everything the server writes to logs lives here."""
from __future__ import annotations

DEFAULT_LANG = 'ru'
LANGS = ('ru', 'en')

MESSAGES = {
    'en': {
        'job.start': 'Generation started',
        'git.version': 'Git found: {version}',
        'git.missing': 'Git is not installed or not in PATH. '
                       'Install it from https://git-scm.com/',
        'git.cmd_failed': 'git {cmd} failed (code {code}): {output}',
        'git.timeout': 'git {cmd} timed out after {seconds} s',
        'repo.dir': 'Working folder: {path}',
        'repo.init': 'Empty git repository initialised (branch main)',
        'identity.set': 'Commit author: {name} <{email}>',
        'identity.global': 'Using global git identity: {name} <{email}>',
        'identity.missing': 'Git author is not configured. Fill in the '
                            'name and e-mail in the form or run '
                            '"git config --global user.name" / '
                            '"git config --global user.email".',
        'plan.summary': 'Plan: {commits} commits on {days} active days '
                        '({first} → {last}), mode: {mode}, seed: {seed}',
        'plan.empty': 'The plan is empty: nothing to commit with these '
                      'settings. Increase the frequency or the period.',
        'day.commits': '{date}: {n} commit(s)',
        'commits.progress': 'Commits created: {done} / {total} ({pct}%)',
        'commits.done': 'All {total} commits created locally',
        'push.remote': 'Remote added: {url}',
        'push.start': 'Pushing to the remote repository '
                      '(may take a while)…',
        'push.ok': 'Push finished successfully',
        'push.fail': 'Push failed. Make sure the remote repository is '
                     'empty (not initialised) and you have access '
                     '(SSH key or a credential manager).',
        'push.skipped': 'Repository URL is not set — push skipped, the '
                        'repository stays local.',
        'job.cancelled': 'Stopped by the user',
        'job.finished': 'Done! Repository: {path}',
        'job.reindex': 'GitHub may need a few minutes to refresh the '
                       'contribution graph.',
        'job.error': 'Unexpected error: {error}',
        'err.type': '"{field}" must be a whole number',
        'err.range': '"{field}" must be between {min} and {max}',
        'err.repository': 'Invalid repository URL. Use '
                          'https://github.com/user/repo.git or '
                          'git@github.com:user/repo.git',
        'err.email': 'Invalid e-mail address',
        'err.invalid': '"{field}" contains invalid characters',
        'err.mode': 'Unknown commit mode',
        'err.output': 'Invalid output folder',
        'err.total_days': 'The period is too long (max {max} days in total)',
        'server.started': 'Server started: {url}',
        'server.stopped': 'Server stopped',
        'server.busy': 'A generation is already running',
        'server.bad_request': 'Bad request',
        'server.forbidden': 'Forbidden',
        'server.not_found': 'Not found',
        'server.no_result': 'There is no finished repository to open',
    },
    'ru': {
        'job.start': 'Генерация запущена',
        'git.version': 'Git найден: {version}',
        'git.missing': 'Git не установлен или не добавлен в PATH. '
                       'Скачайте его: https://git-scm.com/',
        'git.cmd_failed': 'git {cmd} завершился с ошибкой '
                          '(код {code}): {output}',
        'git.timeout': 'git {cmd}: превышено время ожидания ({seconds} с)',
        'repo.dir': 'Рабочая папка: {path}',
        'repo.init': 'Пустой git-репозиторий создан (ветка main)',
        'identity.set': 'Автор коммитов: {name} <{email}>',
        'identity.global': 'Используется глобальная личность git: '
                           '{name} <{email}>',
        'identity.missing': 'Автор git не настроен. Заполните имя и e-mail '
                            'в форме или выполните '
                            '"git config --global user.name" / '
                            '"git config --global user.email".',
        'plan.summary': 'План: {commits} коммитов в {days} активных днях '
                        '({first} → {last}), режим: {mode}, seed: {seed}',
        'plan.empty': 'План пуст: при таких настройках коммитить нечего. '
                      'Увеличьте частоту или период.',
        'day.commits': '{date}: коммитов — {n}',
        'commits.progress': 'Создано коммитов: {done} / {total} ({pct}%)',
        'commits.done': 'Все коммиты ({total}) созданы локально',
        'push.remote': 'Удалённый репозиторий добавлен: {url}',
        'push.start': 'Отправка в удалённый репозиторий '
                      '(может занять время)…',
        'push.ok': 'Push успешно завершён',
        'push.fail': 'Не удалось выполнить push. Убедитесь, что удалённый '
                     'репозиторий пустой (без инициализации) и у вас есть '
                     'доступ (SSH-ключ или менеджер учётных данных).',
        'push.skipped': 'Адрес репозитория не указан — push пропущен, '
                        'репозиторий остался локальным.',
        'job.cancelled': 'Остановлено пользователем',
        'job.finished': 'Готово! Репозиторий: {path}',
        'job.reindex': 'GitHub может обновлять график активности '
                       'несколько минут.',
        'job.error': 'Непредвиденная ошибка: {error}',
        'err.type': '«{field}» должно быть целым числом',
        'err.range': '«{field}» должно быть от {min} до {max}',
        'err.repository': 'Неверный адрес репозитория. Используйте '
                          'https://github.com/user/repo.git или '
                          'git@github.com:user/repo.git',
        'err.email': 'Неверный адрес e-mail',
        'err.invalid': '«{field}» содержит недопустимые символы',
        'err.mode': 'Неизвестный режим коммитов',
        'err.output': 'Неверная папка вывода',
        'err.total_days': 'Слишком длинный период '
                          '(максимум {max} дней суммарно)',
        'server.started': 'Сервер запущен: {url}',
        'server.stopped': 'Сервер остановлен',
        'server.busy': 'Генерация уже выполняется',
        'server.bad_request': 'Некорректный запрос',
        'server.forbidden': 'Доступ запрещён',
        'server.not_found': 'Не найдено',
        'server.no_result': 'Нет готового репозитория, чтобы открыть',
    },
}


def normalize_lang(lang):
    lang = (lang or '').lower()[:2]
    return lang if lang in LANGS else DEFAULT_LANG


def t(lang, key, **params):
    """Translate `key`; falls back to English, then to the key itself."""
    lang = normalize_lang(lang)
    template = MESSAGES[lang].get(key) or MESSAGES['en'].get(key) or key
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError):
        return template
