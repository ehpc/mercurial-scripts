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
5.1. Если в конфигурации указан параметр "forceBranch", происходит переход в указанную ветку;
5.2. Если в конфигурации указан параметр "mapping" и  изменение находится в одной из указанных в параметре веток
     (ключ-значение : исходящая_ветка-входящая_ветка), то происходит переход в указанную входящую ветку;
5.3. Если в конфигурации указан параметр "mapping" и  изменение не находится в одной из указанных в параметре веток
     (ключ-значение : исходящая_ветка-входящая_ветка), но присутствует значение "*": "branch", то происходит переход в указанную в "*" ветку;
5.3. Если в конфигурации указан параметр "mapping" и изменение не находится в одной из указанных в параметре веток
     (ключ-значение : исходящая_ветка-входящая_ветка), то ничего не происходит;
5.4. Иначе происходит переход в ветку, соответствующую входящему изменению;
5.5. Происходит импорт патч-файла в установленную ветку.

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
                    "path": "C:\\data\\fis\\dev\\www\\fcs\\merc\\test2remote", # Репозиторий, в который необходимо склонировать изменения
                    "mapping": { # Маппинг веток
                        "default": "default",
                        "outgoing": "incoming" # Если изменение из ветки "outgoing", то клонировать его в ветку "incoming"
                        # Если ветка входящего изменения здесь не указана, то изменение игнорируется
                        # Если же указано значение "*": "outgoing", то в случае, если ветка входящего изменения не указана, 
                        # изменение клонируется в ветку, указанную в "*"
                    }
                },
                {
                    "path": "C:\\data\\fis\\dev\\www\\fcs\\merc\\test3remote", # Ещё один репозиторий, в который необходимо склонировать изменения
                    "forceBranch": "incoming" # Указывает ветку, в которую склонируются изменения
                },
                {
                    "path": "C:\\data\\fis\\dev\\www\\fcs\\merc\\test4remote"
                    # В этой конфигурации нет дополнительных указаний, поэтому ветка изменения совпадает с веткой репозитория
                }
            ]
        }
    ]
}

"""

import json
import os
from sys import exit
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

def runCommand(cmd, ui):
    """
    Выполняет команду и возвращает строки результата.
    """
    try:
        ui.write(check_output(cmd + '\n', stderr=STDOUT, shell=True))
        return True
    except CalledProcessError as e:
        ui.write('Error: ' + e.output + '\n')
        return False

def getBranchFromMapping(branch, mapping):
    """
    Находит ветку исходящего репозитория, соответствующую ветке входящего изменения.
    """
    if branch in mapping:
        return mapping[branch]
    elif '*' in mapping:
        return mapping['*']
    else:
        return None

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
        cmdResult = runCommand(cmd, ui)
        if cmdResult and os.path.isfile(scriptDir + '/' + node + '.patch'):
            # Для каждого исходящего репозитория
            for remote in remotes:
                path = remote['path']
                # Если указана конкретная ветка, то переносим в неё
                if 'forceBranch' in remote:
                    actualBranch = remote['forceBranch']
                # Если указан маппинг, то переносим согласно нему
                elif 'mapping' in remote:
                    actualBranch = getBranchFromMapping(branch, remote['mapping'])
                # В остальных случаях переносим один к одному
                else:
                    actualBranch = branch
                if actualBranch is not None:
                    # Меняем ветку исходящего репозитория
                    ui.write('Changing branch at {0} to {1}.\n'.format(path, actualBranch))
                    cmd = 'hg update --verbose -R "{0}" {1}'.format(path, actualBranch)
                    ui.write('Command: ' + cmd + '\n')
                    cmdResult = runCommand(cmd, ui)
                    if cmdResult:
                        # Устанавливаем патч-файл в исходящий репозиторий
                        ui.write('Cloning {0} to {1}...\n'.format(node, path))
                        cmd = 'hg import --verbose -R "{0}" "{2}/{1}.patch"'.format(path, node, scriptDir)
                        ui.write('Command: ' + cmd + '\n')
                        runCommand(cmd, ui)
            # Удаляем патч-файл
            ui.write('Cleaning up...\n')
            cmd = 'rm "{1}/{0}.patch"'.format(node, scriptDir)
            ui.write('Command: ' + cmd + '\n')
            cmdResult = runCommand(cmd, ui)
        else:
            ui.write('Failed to create a patch-file at "{}".\n'.format(scriptDir))

"""
Тестовый вывод:
> echo 1 >> test29.txt && hg add && hg commit -m "test" && hg push --verbose
adding test29.txt
pushing to http://mercurial.fisgroup.ru/fcs/web/test1/
searching for changes
1 changesets found
uncompressed size of bundle content:
     218 (changelog)
     172 (manifests)
     139  test29.txt
remote: adding changesets
remote: adding manifests
remote: adding file changes
remote: added 1 changesets with 1 changes to 1 files
remote: Creating a patch-file for 4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d.
remote: Command: hg export --output "/home/merc/mercurial/hooks/4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d.patch" --rev 4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d --verbose -R "/home/merc/fcs/web/test1"
remote: exporting patch:
remote: /home/merc/mercurial/hooks/4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d.patch
remote: Changing branch at /home/merc/fcs/web/test2 to default.
remote: Command: hg update --verbose -R "/home/merc/fcs/web/test2" default
remote: 0 files updated, 0 files merged, 0 files removed, 0 files unresolved
remote: Cloning 4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d to /home/merc/fcs/web/test2...
remote: Command: hg import --verbose -R "/home/merc/fcs/web/test2" "/home/merc/mercurial/hooks/4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d.patch"
remote: applying /home/merc/mercurial/hooks/4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d.patch
remote: patching file test29.txt
remote: adding test29.txt
remote: committing files:
remote: test29.txt
remote: committing manifest
remote: committing changelog
remote: created cd14479648e9
remote: Changing branch at /home/merc/fcs/web/test3 to default.
remote: Command: hg update --verbose -R "/home/merc/fcs/web/test3" default
remote: 0 files updated, 0 files merged, 0 files removed, 0 files unresolved
remote: Cloning 4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d to /home/merc/fcs/web/test3...
remote: Command: hg import --verbose -R "/home/merc/fcs/web/test3" "/home/merc/mercurial/hooks/4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d.patch"
remote: applying /home/merc/mercurial/hooks/4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d.patch
remote: patching file test29.txt
remote: adding test29.txt
remote: committing files:
remote: test29.txt
remote: committing manifest
remote: committing changelog
remote: created 8b77f800c7ab
remote: Cleaning up...
remote: Command: rm "/home/merc/mercurial/hooks/4b3a3a3e107ee61f8168a3e3daf03cd1fa7f6b7d.patch"
"""
