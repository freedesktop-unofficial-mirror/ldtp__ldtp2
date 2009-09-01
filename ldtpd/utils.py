'''
LDTP v2 utils.

@author: Eitan Isaacson <eitan@ascender.com>
@author: Nagappan Alagappan <nagappan@gmail.com>
@copyright: Copyright (c) 2009 Eitan Isaacson
@copyright: Copyright (c) 2009 Nagappan Alagappan
@license: LGPL

http://ldtp.freedesktop.org

This file may be distributed and/or modified under the terms of the GNU General
Public License version 2 as published by the Free Software Foundation. This file
is distributed without any warranty; without even the implied warranty of 
merchantability or fitness for a particular purpose.

See "COPYING" in the source distribution for more information.

Headers in this file shall remain intact.
'''

import re
import pyatspi
from re import match as re_match
from constants import abbreviated_roles
from fnmatch import translate as glob_trans
from server_exception import LdtpServerException

class Utils:
    cached_apps = None
    def __init__(self):
        lazy_load = True
        self._appmap = {}
        self._desktop = pyatspi.Registry.getDesktop(0)
        if Utils.cached_apps is None:
            pyatspi.Registry.registerEventListener(
                self._on_window_event, 'window')
            Utils.cached_apps = set()
            if lazy_load:
                for app in self._desktop:
                    if app is None: continue
                    self.cached_apps.add(app)

    def _on_window_event(self, event):
        self.cached_apps.add(event.host_application)

    def _list_apps(self):
        for app in list(self.cached_apps):
            if not app: continue
            yield app

    def _list_guis(self):
        for app in list(self.cached_apps):
            if not app: continue
            try:
                for gui in app:
                    if not gui: continue
                    yield gui
            except LookupError:
                self.cached_apps.remove(app)

    def _ldtpize_accessible(self, acc):
        label_acc = None
        rel_set = acc.getRelationSet()
        if rel_set:
            for i, rel in enumerate(rel_set):
                relationType = rel.getRelationType()
                if relationType == pyatspi.RELATION_LABELLED_BY or \
                        relationType == pyatspi.RELATION_CONTROLLED_BY:
                    label_acc = rel.getTarget(i)
                    break
        return abbreviated_roles.get(acc.getRole(), 'ukn'), \
            (label_acc or acc).name.replace(' ', '').rstrip(':.')

    def _glob_match(self, pattern, string):
        return bool(re_match(glob_trans(pattern), string))

    def _match_name_to_acc(self, name, acc):
        if acc.name == name:
            return 1
        _object_name = self._ldtpize_accessible(acc)
        _object_name = '%s%s' % (_object_name[0], _object_name[1])
        if _object_name == name:
            return 1
        if self._glob_match(name, acc.name):
            return 1
        if self._glob_match(name, _object_name):
            return 1
        if self._glob_match(re.sub(' ', '', name),
                            re.sub(' ', '', _object_name)):
            return 1
        return 0

    def _match_name_to_appmap(self, name, acc):
        if self._glob_match(name, acc['key']):
            return 1
        if self._glob_match(name, acc['obj_index']):
            return 1
        if self._glob_match(name, acc['label_by']):
            return 1
        if self._glob_match(name, acc['label']):
            return 1
        # Strip space and look for object
        obj_name = '%s' % re.sub(' ', '', name)
        if acc['label_by'] and \
                self._glob_match(obj_name,
                                 re.sub(' ', '', acc['label_by'])):
            return 1
        if acc['label'] and \
                self._glob_match(obj_name,
                                 re.sub(' ', '', acc['label'])):
            return 1
        if self._glob_match(obj_name, acc['key']):
            return 1
        return 0

    def _list_objects(self, obj):
        if obj:
            yield obj
            for child in obj:
                for c in self._list_objects(child):
                    yield c

    def _get_combo_child_object_type(self, obj):
        """
        This function will check for all levels and returns the first
        matching LIST / MENU type
        """
        if obj:
            for child in obj:
                if not child:
                    continue
                if child.childCount > 0:
                    child_obj = self._get_combo_child_object_type(child)
                    if child_obj:
                        return child_obj
                if child.getRole() == pyatspi.ROLE_LIST:
                    return child
                elif child.getRole() == pyatspi.ROLE_MENU:
                    return child

    def _get_child_object_type(self, obj, role_type):
        """
        This function will check for all levels and returns the first
        matching role_type
        """
        if obj and role_type:
            for child in obj:
                if not child:
                    continue
                if child.childCount > 0:
                    child_obj = self._get_child_object_type(child, role_type)
                    if child_obj:
                        return child_obj
                if child.getRole() == role_type:
                    return child

    def _add_appmap_data(self, obj, parent):
        abbrev_role, abbrev_name = self._ldtpize_accessible(obj)
        if abbrev_role in self.ldtpized_obj_index:
            self.ldtpized_obj_index[abbrev_role] += 1
        else:
            self.ldtpized_obj_index[abbrev_role] = 0
        if abbrev_name == '':
            ldtpized_name_base = abbrev_role
            ldtpized_name = '%s%d' % (ldtpized_name_base,
                                      self.ldtpized_obj_index[abbrev_role])
        else:
            ldtpized_name_base = '%s%s' % (abbrev_role, abbrev_name)
            ldtpized_name = ldtpized_name_base
        i = 0
        while ldtpized_name in self.ldtpized_list:
            i += 1
            ldtpized_name = '%s%d' % (ldtpized_name_base, i)
        if parent in self.ldtpized_list:
            self.ldtpized_list[parent]['children'].append(ldtpized_name)
        self.ldtpized_list[ldtpized_name] = {'key' : ldtpized_name,
                                             'parent' : parent,
                                             'class' : obj.getRoleName().replace(' ', '_'),
                                             'child_index' : obj.getIndexInParent(),
                                             'children' : [],
                                             'obj_index' : '%s#%d' % (abbrev_role,
                                                                      self.ldtpized_obj_index[abbrev_role]),
                                             'label' : obj.name,
                                             'label_by' : '',
                                             'description' : obj.description
                                             }
        return ldtpized_name

    def _populate_appmap(self, obj, parent, child_index):
        if obj:
            if child_index != -1:
                parent = self._add_appmap_data(obj, parent)
            for child in obj:
                if not child:
                    continue
                if child.getRole() == pyatspi.ROLE_TABLE_CELL:
                    break
                self._populate_appmap(child, parent, child.getIndexInParent())

    def _appmap_pairs(self, gui, force_remap = False):
        self.ldtpized_list = {}
        self.ldtpized_obj_index = {}
        if not force_remap:
            for key in self._appmap.keys():
                if self._match_name_to_acc(key, gui):
                    return self._appmap[key]
        abbrev_role, abbrev_name = self._ldtpize_accessible(gui)
        _window_name = '%s%s' % (abbrev_role, abbrev_name)
        abbrev_role, abbrev_name = self._ldtpize_accessible(gui.parent)
        _parent = abbrev_name
        self._populate_appmap(gui, _parent, gui.getIndexInParent())
        self._appmap[_window_name] = self.ldtpized_list
        return self.ldtpized_list

    def _get_menu_hierarchy(self, window_name, object_name):
        _menu_hierarchy = re.split(';', object_name)
        if not re.search('^mnu', _menu_hierarchy[0]):
            _menu_hierarchy[0] = 'mnu%s' % _menu_hierarchy[0]
        obj = self._get_object(window_name, _menu_hierarchy[0])
        for _menu in _menu_hierarchy[1:]:
            _flag = False
            for _child in self._list_objects(obj):
                if obj == _child:
                    # if the given object and child object matches
                    continue
                if self._match_name_to_acc(_menu, _child):
                    _flag = True
                    obj = _child
                    break
            if not _flag:
                raise LdtpServerException (
                    'Menu item "%s" doesn\'t exist in hierarchy' % _menu)
        return obj

    def _click_object(self, obj, action = 'click'):
        try:
            iaction = obj.queryAction()
        except NotImplementedError:
            raise LdtpServerException(
                'Object does not have an Action interface')
        else:
            for i in xrange(iaction.nActions):
                if iaction.getName(i) == action:
                    iaction.doAction(i)
                    return
            raise LdtpServerException('Object does not have a "%s" action' % action)

    def _get_object_in_window(self, appmap, obj_name):
        for name in appmap.keys():
            obj = appmap[name]
            if self._match_name_to_appmap(obj_name, obj):
                return obj
        return None

    def _get_window_handle(self, window_name):
        window_list = []
        window_type = {}

        # Search with accessible name
        for gui in self._list_guis():
            if self._match_name_to_acc(window_name, gui):
                return gui

        # Search with LDTP appmap format
        for gui in self._list_guis():
            w_name = self._ldtpize_accessible(gui)
            if w_name[1] == '':
                if w_name[0] in window_type:
                    window_type[w_name[0]] += 1
                else:
                    window_type[w_name[0]] = 0
                tmp_name = '%d' % window_type[w_name[0]]
            else:
                tmp_name = w_name[1]
            w_name = tmp_name = '%s%s' % (w_name[0], tmp_name)
            index = 1
            while w_name in window_list:
                w_name = '%s%d' % (tmp_name, index)
                index += 1
            window_list.append(w_name)
            if window_name == w_name:
                return gui
            if self._glob_match(window_name, w_name):
                return gui
            if self._glob_match(window_name, w_name):
                return gui
            if self._glob_match(re.sub(' ', '', window_name),
                                re.sub(' ', '', w_name)):
                return gui
        return None

    def _get_object(self, window_name, obj_name):
        _window_handle = self._get_window_handle(window_name)
        if not _window_handle:
            raise LdtpServerException('Unable to find window "%s"' % \
                                          window_name)
        appmap = self._appmap_pairs(_window_handle)
        obj = self._get_object_in_window(appmap, obj_name)
        # while time_diff < 3
        if not obj:
            appmap = self._appmap_pairs(_window_handle, force_remap = True)
            obj = self._get_object_in_window(appmap, obj_name)
        if not obj:
            raise LdtpServerException(
                'Unable to find object name "%s" in application map' % obj_name)
            
        def _traverse_parent(gui, window_name, obj, parent_list):
            if obj and window_name:
                parent = obj['parent']
                parent_list.append(parent)
                if self._match_name_to_acc(parent, gui):
                    return parent_list
                return _traverse_parent(gui, window_name,
                                        appmap[parent],
                                        parent_list)

        _parent_list = _traverse_parent(_window_handle, window_name, obj, [])
        if not _parent_list:
            raise LdtpServerException(
                'Unable to find object name "%s" in application map' % obj_name)
        _parent_list.reverse()
        key = obj['key']
        if key:
            _parent_list.append(key)
        obj = _window_handle
        for key in _parent_list[1:]:
            if key in appmap and obj:
                obj = obj.getChildAtIndex(appmap[key]['child_index'])
        return obj

    def _grab_focus(self, obj):
        try:
            componenti = obj.queryComponent()
        except:
            raise LdtpServerException('Failed to grab focus for %s' % obj)
        componenti.grabFocus()

    def _get_accessible_at_row_column(self, obj, row_index, column_index):
        try:
            tablei = obj.queryTable()
        except NotImplementedError:
            raise LdtpServerException('Object not table type.')

        if row_index < 0 or row_index > tablei.nRows:
            raise LdtpServerException('Row index out of range: %d' % row_index)

        if column_index < 0 or column_index > tablei.nColumns:
            raise LdtpServerException('Column index out of range: %d' % \
                                          column_index)

        cell = tablei.getAccessibleAt(row_index, column_index)
        if not cell:
            raise LdtpServerException('Unable to access table cell on ' \
                                          'the given row and column index')
        return cell

    def _check_state(self, obj, object_state):
        _state = obj.getState()
        _current_state = _state.getStates()

        _status = False
        if object_state in _current_state:
            _status = True

        return _status

    def _mouse_event(self, x, y, name = 'b1c'):
        pyatspi.Registry.generateMouseEvent(x, y, name)

        return 1

    def _get_size(self, obj):
        try:
            componenti = obj.queryComponent()
        except:
            raise LdtpServerException('Failed to grab focus for %s' % obj)
        return componenti.getExtents(pyatspi.DESKTOP_COORDS)
