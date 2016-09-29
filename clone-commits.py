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
from subprocess import check_output, call, STDOUT, CalledProcessError
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

def runCommand(cmd):
    """
    Выполняет команду и возвращает строки результата.
    """
    try:
        return check_output(cmd + '\n', stderr=STDOUT, shell=True)
    except CalledProcessError as e:
        return 'Error: ' + e.output + '\n'

def cloneCommitsHook(ui, repo, **kwargs):
    """
    Хук, который выполняет при событии "incoming", т.е. при каждом входящем изменении в репозиторий.
    Если кто-то отправил 4 коммита одним пушем, то входящих будет 4 штуки и для каждого вызовется этот хук.
    """
    # Получаем список ссылок на репозитории, в которые клонировать изменение
    remotes = getReposToPushTo(repo)
    # Если таковые имеются
    if len(remotes):
        # Идентификатор изменения
        node = kwargs['node']
        # Ветка, в которой находится изменение
        branch = repo[node].branch()
        # Создаём патч-файл
        ui.write('Creating a patch-file for {0}.\n'.format(node))
        cmd = 'hg export --output "{1}/{0}.patch" --rev {0} --verbose -R "{2}"'.format(node, scriptDir, repo.root)
        ui.write('Command: ' + cmd + '\n')
        ui.write(runCommand(cmd))
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
                cmd = 'hg update --verbose -R "{0}" {1}'.format(path, actualBranch)
                ui.write('Command: ' + cmd + '\n')
                ui.write(runCommand(cmd))
                # Устанавливаем патч-файл в исходящий репозиторий
                ui.write('Cloning {0} to {1}...\n'.format(node, path))
                cmd = 'hg import --verbose -R "{0}" "{2}/{1}.patch"'.format(path, node, scriptDir)
                ui.write('Command: ' + cmd + '\n')
                ui.write(runCommand(cmd))
            # Удаляем патч-файл
            ui.write('Cleaning up...\n')
            cmd = 'rm "{1}/{0}.patch"'.format(node, scriptDir)
            ui.write('Command: ' + cmd + '\n')
            ui.write(runCommand(cmd))
        else:
            ui.write('Failed to create a patch-file at "{}".\n'.format(scriptDir))

"""
Тестовый вывод:
> echo 1 >> test16.txt && hg add && hg commit -m "test1" && hg push --verbose
adding test16.txt
pushing to http://mercurial.fisgroup.ru/fcs/web/test1/
searching for changes
1 changesets found
uncompressed size of bundle content:
     202 (changelog)
     172 (manifests)
     139  test16.txt
remote: adding changesets
remote: adding manifests
remote: adding file changes
remote: added 1 changesets with 1 changes to 1 files
remote: Creating a patch-file for 2a2f26d98c9b1f382fc69895f3e619d12f97b629.
remote: Command: hg export --output "/home/merc/hooks/2a2f26d98c9b1f382fc69895f3e619d12f97b629.patch" --rev 2a2f26d98c9b1f382fc69895f3e619d12f97b629 --verbose -R "/home/merc/fcs/web/test1"
remote: exporting patch:
remote: /home/merc/hooks/2a2f26d98c9b1f382fc69895f3e619d12f97b629.patch
remote: Changing branch at /home/merc/fcs/web/test2 to default.
remote: Command: hg update --verbose -R "/home/merc/fcs/web/test2" default
remote: 0 files updated, 0 files merged, 0 files removed, 0 files unresolved
remote: Cloning 2a2f26d98c9b1f382fc69895f3e619d12f97b629 to /home/merc/fcs/web/test2...
remote: Command: hg import --verbose -R "/home/merc/fcs/web/test2" "/home/merc/hooks/2a2f26d98c9b1f382fc69895f3e619d12f97b629.patch"
remote: applying /home/merc/hooks/2a2f26d98c9b1f382fc69895f3e619d12f97b629.patch
remote: patching file test16.txt
remote: adding test16.txt
remote: committing files:
remote: test16.txt
remote: committing manifest
remote: committing changelog
remote: created 7fd2a5161b2b
remote: Changing branch at /home/merc/fcs/web/test3 to default.
remote: Command: hg update --verbose -R "/home/merc/fcs/web/test3" default
remote: 0 files updated, 0 files merged, 0 files removed, 0 files unresolved
remote: Cloning 2a2f26d98c9b1f382fc69895f3e619d12f97b629 to /home/merc/fcs/web/test3...
remote: Command: hg import --verbose -R "/home/merc/fcs/web/test3" "/home/merc/hooks/2a2f26d98c9b1f382fc69895f3e619d12f97b629.patch"
remote: applying /home/merc/hooks/2a2f26d98c9b1f382fc69895f3e619d12f97b629.patch
remote: patching file test16.txt
remote: adding test16.txt
remote: committing files:
remote: test16.txt
remote: committing manifest
remote: committing changelog
remote: created 57dbcab3dc96
remote: Cleaning up...
remote: Command: rm "/home/merc/hooks/2a2f26d98c9b1f382fc69895f3e619d12f97b629.patch"
"""
