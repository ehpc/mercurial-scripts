# -*- coding: utf-8 -*-
"""
Клонирует коммиты при входящих изменениях в другие репозитории

Состав утилиты:
1. Головной файл clone-commits.py;
2. Настроечный файл clone-commits.json.

Системные требования:
1. Hg 3.8.4+;
2. Python 2.7.12+.

Условия корректной работы:
1. Все репозитории должны быть локальными, т.е. находиться в одном файловом пространстве;
2. Хук должен быть установлен на стороне сервера.

Установка утилиты:
1. Поместить файлы в рабочую папку, например /home/merc/hooks/;
2. Раздать необходимые права;
3. Добавить в глобальный hgrc (например, /etc/mercurial/hgrc) включение хука:
[hooks]
incoming.cloneCommits = python:/home/merc/hooks/clone-commits.py:cloneCommitsHook

Принцип работы:
1. При входящих изменениях в удалённый репозиторий (когда кто-то делает пуш) срабатывает хук;
2. Хук срабатывает один раз для каждого входящего коммита;
3. Происходит поиск конфигурации в clone-commits.json, соответсвующей адресу входящего (from) репозитория (repo.root);
4. Создаётся патч-файл входящего изменения;
5. Для каждого исходящего (to) репозитория из конфигурации:
5.1. Если в конфигурации указан параметр "forceBranch", происходит переход в указанную ветку, иначе:
5.1.1 Происходит переход в ветку, соответствующую входящему изменению;
5.2. Происходит импорт патч-файла в установленную ветку.

Настройка:
Пример файла clone-commits.json:
{
    "mapping": [
        {
            "from": {
                "path": "C:\\data\\fis\\dev\\www\\fcs\\merc\\test1remote" # Репозиторий, в который пришли входящие изменения
            },
            "to": [
                {
                    "path": "C:\\data\\fis\\dev\\www\\fcs\\merc\\test2remote" # Репозиторий, в который необходимо склонировать изменения
                },
                {
                    "path": "C:\\data\\fis\\dev\\www\\fcs\\merc\\test3remote", # Ещё один репозиторий, в который необходимо склонировать изменения
                    "forceBranch": "incoming" # Указывает ветку, в которую склонируются изменения
                }
            ]
        }
    ]
}

"""

import json
import os
from mercurial import ui, hg, cmdutil, commands
from mercurial.i18n import _
from subprocess import check_output, call
from pprint import pprint

scriptDir = os.path.dirname(os.path.abspath(__file__))

def getReposToPushTo(repo):
    """
    Получает список ссылок на репозитории, в которые следует клонировать коммит.
    """
    # Подгружаем файл конфигураций
    with open(scriptDir + '/clone-commits.json') as configFile:
        config = json.load(configFile)
    # Ищем конфигурацию для нашего репозитория
    config = [mapping['to'] for mapping in config['mapping'] if mapping['from']['path'] == repo.root] # repo.root = repo.path
    return config[0] if config else []

def cloneCommitsHook(ui, repo, **kwargs):
    """
    Хук, который выполняет при событии "incoming", т.е. при каждом входящем изменении в репозиторий.
    Если кто-то отправил 4 коммита одним пушем, то входящих будет 4 штуки и для каждого вызовется этот хук.
    """
    # Получаем список ссылок на репозитории, в которые клонировать изменение
    remotes = getReposToPushTo(repo)
    # Идентификатор изменения
    node = kwargs['node']
    # Ветка, в которой находится изменение
    branch = repo[node].branch()
    # Создаём патч-файл
    ui.write('Creating a patch-file for {0}.\n'.format(node))
    call('hg export --output "{1}/{0}.patch" --rev {0} --verbose'.format(node, scriptDir), shell=True)
    if os.path.isfile(scriptDir + '/' + node + '.patch'):
        # Для каждого исходящего репозитория
        for remote in remotes:
            path = remote['path']
            # Если указана конкретная ветка, то переносим в неё
            if 'forceBranch' in remote:
                actualBranch = remote['forceBranch']
            else:
                actualBranch = branch
            # Меняем ветку исходящего репозитория
            ui.write('Changing branch at {0} to {1}.\n'.format(path, actualBranch))
            call('hg update --verbose -R "{0}" {1}'.format(path, actualBranch), shell=True)
            # Устанавливаем патч-файл в исходящий репозиторий
            ui.write('Cloning {0} to {1}...\n'.format(node, path))
            call('hg import --verbose -R "{0}" "{2}/{1}.patch"'.format(path, node, scriptDir), shell=True)
        # Удаляем патч-файл
        call('rm "{1}/{0}.patch"'.format(node, scriptDir), shell=True)
    else:
        ui.write('Failed to create a patch-file at "{}".\n'.format(scriptDir))

"""
Тестовый вывод:
> echo 1 >> test4.txt && hg add && hg commit -m "test1" && hg push --verbose
pushing to C:\data\fis\dev\www\fcs\merc\test1remote
searching for changes
1 changesets found
uncompressed size of bundle content:
     191 (changelog)
     171 (manifests)
     138  test4.txt
adding changesets
adding manifests
adding file changes
added 1 changesets with 1 changes to 1 files
calling hook incoming.cloneCommits: hghook_incoming_cloneCommits.cloneCommitsHook
Creating a patch-file for 99b25cb2cafd430011e04c9d7ca15f01206aca71.
exporting patch:
C:\Users\ehpc\Dropbox\projects\dev\mercurial/99b25cb2cafd430011e04c9d7ca15f01206aca71.patch
Changing branch at C:\data\fis\dev\www\fcs\merc\test2remote to default.
0 files updated, 0 files merged, 0 files removed, 0 files unresolved
Cloning 99b25cb2cafd430011e04c9d7ca15f01206aca71 to C:\data\fis\dev\www\fcs\merc\test2remote...
applying C:\Users\ehpc\Dropbox\projects\dev\mercurial/99b25cb2cafd430011e04c9d7ca15f01206aca71.patch
patching file test4.txt
Hunk #1 succeeded at 8 (offset -7 lines).
committing files:
test4.txt
committing manifest
committing changelog
created f2595edd2148
Changing branch at C:\data\fis\dev\www\fcs\merc\test3remote to incoming.
0 files updated, 0 files merged, 0 files removed, 0 files unresolved
Cloning 99b25cb2cafd430011e04c9d7ca15f01206aca71 to C:\data\fis\dev\www\fcs\merc\test3remote...
applying C:\Users\ehpc\Dropbox\projects\dev\mercurial/99b25cb2cafd430011e04c9d7ca15f01206aca71.patch
patching file test4.txt
Hunk #1 succeeded at 4 (offset -11 lines).
committing files:
test4.txt
committing manifest
committing changelog
created cdc471b0f5da
"""
