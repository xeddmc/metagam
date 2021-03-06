#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

import mg
from cassandra.ttypes import *
import logging
import re
import json
import time
from mg.core.tools import *

class CassandraMaintenance(mg.Module):
    def register(self):
        self.rhook("cassmaint.validate", self.validate)

    def validate(self, app, cls):
        objclasses = {}
        app.hooks.call("objclasses.list", objclasses)
        cinfo = objclasses.get(cls)
        if not cinfo:
            self.call("web.not_found")
        self.debug("Cassandra validation. app=%s, cls=%s", app.tag, cls)
        # loading list of object UUIDS
        uuids = app.db.dump_objects(cls)
        obj_cnt = len(uuids)
        self.debug("Objects count: %d", obj_cnt)
        index_cnt = 0
        missing_cnt = 0
        orphaned_cnt = 0
        try:
            index_list = cinfo[0].indexes
        except AttributeError:
            pass
        else:
            # loading all indexes into memory
            indexes = {}
            for index_name, index_desc in index_list.iteritems():
                index_data = app.db.dump_index(cls, index_name)
                index_cnt += len(index_data)
                self.debug("Index %s entries: %s", index_name, len(index_data))
                indexes[index_name] = index_data
            # iterating over objects and checking their indexes
            for uuid in uuids:
                obj = app.obj(cinfo[0], uuid)
                restore = False
                for index_name, lst in obj.index_values().iteritems():
                    key = utf2str(lst[0])
                    column = utf2str(lst[1])
                    try:
                        index = indexes[index_name]
                        objects = index[key][2]
                        del objects[column]
                        if not objects:
                            del index[key]
                            if not index:
                                del indexes[index_name]
                    except KeyError:
                        missing_cnt += 1
                        self.debug("  - object %s is missing index %s (key %s, column %s)", obj.uuid, index_name, key, column)
                        restore = True
                if restore:
                    obj.touch()
                    obj._indexes = {}
                    obj.store()
            # iterating over remaining indexes and deleting them from the DB
            for index_name, index_data in indexes.iteritems():
                self.debug("Listing invalid keys in index %s", index_name)
                for index_value, index_data2 in index_data.iteritems():
                    self.debug("  - Listing invalid values for value %s", index_value)
                    family = index_data2[0]
                    key = index_data2[1]
                    for column in index_data2[2].keys():
                        orphaned_cnt += 1
                        self.debug("    - %s/%s/%s", family, key, column)
                        timestamp = app.db.get_time()
                        mutation = Mutation(deletion=Deletion(predicate=SlicePredicate([column]), timestamp=timestamp))
                        mutations = {key: {family: [mutation]}}
                        app.db.batch_mutate(mutations, ConsistencyLevel.QUORUM)
        # returning statistics
        return {
            "obj": obj_cnt,
            "index": index_cnt,
            "missing": missing_cnt,
            "orphaned": orphaned_cnt
        }

class CassandraMonitor(mg.Module):
    def register(self):
        self.rhook("cassandra.register", self.register_cassandra)

    def register_cassandra(self):
        inst = self.app().inst
        # Register service
        int_app = inst.int_app
        srv = mg.SingleApplicationWebService(self.app(), "%s-cassandra" % inst.instid, "cassandra", "cass")
        srv.serve_any_port()
        int_app.call("cluster.register-service", srv)
