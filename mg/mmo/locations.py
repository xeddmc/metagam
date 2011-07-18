from mg import *
from mg.constructor import *
from mg.mmo.locations_classes import *
import cStringIO
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageFilter
import re

re_polygon_param = re.compile(r'^polygon-(\d+)$')

class LocationsAdmin(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-locations.index", self.menu_locations_index)
        self.rhook("ext-admin-locations.editor", self.admin_locations_editor, priv="locations.editor")
        self.rhook("headmenu-admin-locations.editor", self.headmenu_locations_editor)
        self.rhook("ext-admin-locations.config", self.admin_locations_config, priv="locations.config")
        self.rhook("headmenu-admin-locations.config", self.headmenu_locations_config)

    def child_modules(self):
        lst = ["mg.mmo.locations.LocationsStaticImages", "mg.mmo.locations.LocationsStaticImagesAdmin"]
        return lst

    def menu_root_index(self, menu):
        menu.append({"id": "locations.index", "text": self._("Locations"), "order": 20})

    def menu_locations_index(self, menu):
        menu.append({"id": "locations/editor", "text": self._("Locations editor"), "order": 0, "leaf": True})
        menu.append({"id": "locations/config", "text": self._("Locations configuration"), "order": 1, "leaf": True})

    def permissions_list(self, perms):
        perms.append({"id": "locations.editor", "name": self._("Locations editor")})
        perms.append({"id": "locations.config", "name": self._("Locations configuration")})

    def headmenu_locations_editor(self, args):
        if args == "new":
            return [self._("New location"), "locations/editor"]
        elif args:
            location = self.location(args)
            if location.valid():
                return [location.name, "locations/editor"]
            else:
                return [self._("Editor"), "locations/editor"]
        return self._("Locations")

    def admin_locations_editor(self):
        req = self.req()
        if req.args:
            if req.args != "new":
                location = self.location(req.args)
                if not location.valid():
                    self.call("web.response_json", {"success": True, "redirect": "locations/editor"})
                db_loc = location.db_location
            else:
                db_loc = self.obj(DBLocation)
            lang = self.call("l10n.lang")
            if req.ok():
                self.call("web.upload_handler")
                errors = {}
                name = req.param("name")
                if not name:
                    errors["name"] = self._("Name is mandatory")
                elif name != htmlescape(name) or name != jsencode(name):
                    errors["name"] = self._("Name contains forbidden symbols")
                else:
                    db_loc.set("name", name)
                if lang == "ru":
                    if req.param("name_g"):
                        db_loc.set("name_g", req.param("name_g"))
                    else:
                        db_loc.delkey("name_g")
                    if req.param("name_a"):
                        db_loc.set("name_a", req.param("name_a"))
                    else:
                        db_loc.delkey("name_a")
                    if req.param("name_w"):
                        db_loc.set("name_w", req.param("name_w"))
                    else:
                        db_loc.delkey("name_w")
                    if req.param("name_t"):
                        db_loc.set("name_t", req.param("name_t"))
                    else:
                        db_loc.delkey("name_t")
                    if req.param("name_f"):
                        db_loc.set("name_f", req.param("name_f"))
                    else:
                        db_loc.delkey("name_f")
                db_loc.set("image_type", req.param("v_image_type"))
                flags = {}
                self.call("admin-locations.editor-form-validate", db_loc, flags, errors)
                if not flags.get("image_type_valid"):
                    errors["v_image_type"] = self._("Select valid image type")
                # errors
                if len(errors):
                    self.call("web.response_json_html", {"success": False, "errors": errors})
                # storing
                self.call("admin-locations.editor-form-store", db_loc, flags)
                db_loc.store()
                self.call("admin-locations.editor-form-cleanup", db_loc, flags)
                self.call("web.response_json_html", {"success": True, "redirect": "locations/editor/%s" % location.uuid, "parameters": {"saved": 1}})
            # rendering form
            fields = []
            fields.append({"name": "name", "value": db_loc.get("name"), "label": self._("Location name")})
            if lang == "ru":
                fields.append({"name": "name_g", "value": db_loc.get("name_g"), "label": self._("Location name in genitive")})
                fields.append({"name": "name_a", "value": db_loc.get("name_a"), "label": self._("Location name in accusative"), "inline": True})
                fields.append({"name": "name_w", "value": db_loc.get("name_w"), "label": self._("Location name (where?) - 'in the Some Location'")})
                fields.append({"name": "name_t", "value": db_loc.get("name_t"), "label": self._("Location name (to where?) - 'to the Some Location'"), "inline": True})
                fields.append({"name": "name_f", "value": db_loc.get("name_f"), "label": self._("Location name (from where?) - 'from the Some Location'"), "inline": True})
            image_type = {"name": "image_type", "type": "combo", "value": db_loc.get("image_type"), "label": self._("Image type"), "values": []}
            fields.append(image_type)
            self.call("admin-locations.editor-form-render", db_loc, fields)
            if not db_loc.get("image_type") and image_type["values"] and not image_type["value"]:
                image_type["value"] = image_type["values"][0][0]
            # rendering location preview
            if req.args != "new":
                html = self.call("admin-locations.render", location)
                if html:
                    fields.insert(0, {"type": "html", "html": html})
            self.call("admin.form", fields=fields, modules=["FileUploadField"])
        rows = []
        locations = []
        lst = self.objlist(DBLocationList, query_index="all")
        lst.load()
        for db_loc in lst:
            row = [
                db_loc.get("name"),
                None,
                '<hook:admin.link href="locations/editor/%s" title="%s" />' % (db_loc.uuid, self._("edit")),
            ]
            rows.append(row)
            locations.append({
                "db_loc": db_loc,
                "row": row
            })
        table = {
            "links": [
                {
                    "hook": "locations/editor/new",
                    "text": self._("New location"),
                    "lst": True,
                }
            ],
            "header": [
                self._("Location"),
                self._("Functions"),
                self._("Editing"),
            ],
            "rows": rows,
        }
        self.call("admin-locations.format-list", locations, table)
        vars = {
            "tables": [table]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_locations_config(self, args):
        return self._("Locations configuration")

    def admin_locations_config(self):
        req = self.req()
        if req.ok():
            errors = {}
            config = self.app().config_updater()
            start_location = req.param("v_start_location")
            if start_location:
                loc = self.location(start_location)
                if not loc.valid():
                    errors["v_start_location"] = self._("Invalid starting location")
                config.set("locations.startloc", start_location)
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Settings stored"), {})
        lst = self.objlist(DBLocationList, query_index="all")
        lst.load()
        locations = [(db_loc.uuid, db_loc.get("name")) for db_loc in lst]
        fields = [
            {"name": "start_location", "label": self._("Starting location for the new character"), "type": "combo", "value": self.conf("locations.startloc"), "values": locations, "allow_blank": True},
        ]
        self.call("admin.form", fields=fields)

class LocationsStaticImages(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("locations.render", self.render)

    def render(self, location):
        if location.image_type == "static":
            zones = []
            for zone in location.db_location.get("static_zones"):
                zones.append({
                    "polygon": zone.get("polygon"),
                    "action": zone.get("action"),
                    "loc": zone.get("loc"),
                })
            vars = {
                "loc": {
                    "id": location.uuid,
                    "image": location.db_location.get("image_static"),
                },
                "zones": zones,
            }
            design = self.design("gameinterface")
            raise Hooks.Return(self.call("design.parse", design, "location-static.html", None, vars))

class LocationsStaticImagesAdmin(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("admin-locations.editor-form-render", self.form_render)
        self.rhook("admin-locations.editor-form-validate", self.form_validate)
        self.rhook("admin-locations.editor-form-store", self.form_store)
        self.rhook("admin-locations.editor-form-cleanup", self.form_cleanup)
        self.rhook("ext-admin-locations.image-map", self.admin_image_map, priv="locations.editor")
        self.rhook("headmenu-admin-locations.image-map", self.headmenu_image_map)
        self.rhook("admin-locations.render", self.render)

    def form_render(self, db_loc, fields):
        for fld in fields:
            if fld["name"] == "image_type":
                fld["values"].append(("static", self._("Static image")))
        fields.append({"name": "image_static", "type": "fileuploadfield", "label": self._("Replace location image (if necessary)") if db_loc.get("image_static") else self._("Upload location image"), "condition": "[image_type]=='static'"})

    def form_validate(self, db_loc, flags, errors):
        req = self.req()
        if db_loc.get("image_static"):
            flags["old_image_static"] = db_loc.get("image_static")
        if req.param("v_image_type") == "static":
            flags["image_type_valid"] = True
            image_data = req.param_raw("image_static")
            if image_data:
                try:
                    image_obj = Image.open(cStringIO.StringIO(image_data))
                    if image_obj.load() is None:
                        raise IOError
                except IOError:
                    errors["image_static"] = self._("Image format not recognized")
                except OverflowError:
                    errors["image_static"] = self._("Image format not recognized")
                else:
                    width, height = image_obj.size
                    flags["image_static"] = image_data
                    flags["image_static_w"] = width
                    flags["image_static_h"] = height
                    if image_obj.format == "GIF":
                        flags["image_static_ext"] = "gif"
                        flags["image_static_content_type"] = "image/gif"
                    elif image_obj.format == "PNG":
                        flags["image_static_ext"] = "png"
                        flags["image_static_content_type"] = "image/png"
                    elif image_obj.format == "JPEG":
                        flags["image_static_ext"] = "jpg"
                        flags["image_static_content_type"] = "image/jpeg"
                    else:
                        del flags["image_static"]
                        del flags["image_static_w"]
                        del flags["image_static_h"]
                        errors["image_static"] = self._("Image format must be GIF, JPEG or PNG")
            else:
                if db_loc.get("image_static"):
                    flags["old_image_static"] = db_loc.get("image_static")
                else:
                    errors["image_static"] = self._("Upload an image")
        else:
            db_loc.delkey("image_static")
            db_loc.delkey("image_static_w")
            db_loc.delkey("image_static_h")

    def form_store(self, db_loc, flags):
        if flags.get("image_static"):
            uri = self.call("cluster.static_upload", "locations", flags["image_static_ext"], flags["image_static_content_type"], flags["image_static"])
            db_loc.set("image_static", uri)
            db_loc.set("image_static_w", flags["image_static_w"])
            db_loc.set("image_static_h", flags["image_static_h"])

    def form_cleanup(self, db_loc, flags):
        if flags.get("old_image_static") and db_loc.get("image_static") != flags["old_image_static"]:
            self.call("cluster.static_delete", flags["old_image_static"])

    def headmenu_image_map(self, args):
        return [self._("Map"), "locations/editor/%s" % args]

    def admin_image_map(self):
        req = self.req()
        location = self.location(req.args)
        if not location.valid() or location.image_type != "static":
            self.call("admin.redirect", "locations/editor")
        if req.ok():
            zones = {}
            errors = {}
            for key in req.param_dict().keys():
                m = re_polygon_param.match(key)
                if m:
                    zone_id = int(m.group(1))
                    zone = {}
                    zones[zone_id] = zone
                    # polygon data
                    zone["polygon"] = req.param("polygon-%d" % zone_id)
                    poly = zone["polygon"].split(",")
                    if len(poly) == 0:
                        errors["polygon-%d" % zone_id] = self._("Polygon may not be empty")
                    elif len(poly) % 2:
                        errors["polygon-%d" % zone_id] = self._("Odd number of coordinates")
                    elif len(poly) < 6:
                        errors["polygon-%d" % zone_id] = self._("Minimal number of points is 3")
                    else:
                        for coo in poly:
                            if not valid_int(coo):
                                errors["polygon-%d" % zone_id] = self._("Invalid non-integer coordinate encountered")
                                break
                    # hint
                    hint = req.param("hint-%d" % zone_id).strip()
                    if hint:
                        zone["hint"] = hint
                    # action
                    action = req.param("v_action-%d" % zone_id)
                    zone["action"] = action;
                    if action == "none":
                        del zone["action"]
                    elif action == "move":
                        loc = req.param("v_location-%d" % zone_id)
                        if not loc:
                            errors["v_location-%d" % zone_id] = self._("Location not specified")
                        else:
                            loc_obj = self.location(loc)
                            if not loc_obj.valid():
                                errors["v_location-%d" % zone_id] = self._("Invalid location specified")
                            else:
                                zone["loc"] = loc
                    else:
                        errors["v_action-%d" % zone_id] = self._("No action specified")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            location.db_location.set("static_zones", [zones[zone_id] for zone_id in sorted(zones.keys())])
            location.db_location.store()
            self.call("web.response_json", {"success": True, "redirect": "locations/image-map/%s" % location.uuid, "parameters": {"saved": 1}})
        # Loading zones
        zones = []
        for zone in location.db_location.get("static_zones"):
            zones.append({
                "polygon": zone.get("polygon"),
                "hint": jsencode(zone.get("hint")),
                "action": zone.get("action", "none"),
                "loc": zone.get("loc")
            })
        # Loading locations
        locations = []
        lst = self.objlist(DBLocationList, query_index="all")
        lst.load()
        for db_loc in lst:
            locations.append({
                "id": db_loc.uuid,
                "name": jsencode(db_loc.get("name"))
            })
        vars = {
            "image": location.db_location.get("image_static"),
            "width": location.db_location.get("image_static_w"),
            "height": location.db_location.get("image_static_h"),
            "ie_warning": self._("Warning! Internet Explorer browser is not supported. Location editor may work slowly and unstable. Mozilla Firefox, Google Chrome and Opera are fully supported"),
            "submit_url": "/admin-locations/image-map/%s" % location.uuid,
            "zones": zones,
            "actions": [("none", self._("No action")), ("move", self._("Move to another location"))],
            "locations": locations,
            "LocationEditor": self._("Switch to the location editor"),
            "loc": {
                "id": location.uuid,
            },
        }
        req = self.req()
        if req.param("saved"):
            vars["saved"] = {"text": self._("Location saved successfully")}
        self.call("admin.response_template", "admin/locations/imagemap.html", vars)

    def render(self, location):
        if location.image_type == "static":
            zones = []
            for zone in location.db_location.get("static_zones"):
                zones.append({
                    "polygon": zone.get("polygon"),
                    "action": zone.get("action"),
                    "loc": zone.get("loc"),
                })
            vars = {
                "loc": {
                    "id": location.uuid,
                    "image": location.db_location.get("image_static"),
                },
                "zones": zones,
                "MapEditor": self._("Switch to the image map editor"),
            }
            req = self.req()
            if req.param("saved"):
                vars["saved"] = {"text": self._("Image map saved successfully")}
            raise Hooks.Return(self.call("web.parse_layout", "admin/locations/imagemap-render.html", vars))

class Locations(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("locations.character_get", self.get)
        self.rhook("locations.character_before_set", self.before_set)
        self.rhook("locations.character_set", self.lset)
        self.rhook("locations.character_after_set", self.after_set)
        self.rhook("ext-location.index", self.ext_location, priv="logged")
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("ext-location.move", self.ext_move, priv="logged")

    def get(self, character):
        try:
            info = self.obj(DBCharacterLocation, character.uuid)
        except ObjectNotFoundException:
            start_location = self.conf("locations.startloc")
            if start_location:
                info = self.obj(DBCharacterLocation, character.uuid, data={})
                info.set("location", start_location)
                info.store()
                loc = self.location(start_location)
                self.after_set(character, loc, None)
                delay = None
            else:
                loc = None
                instance = None
                delay = None
        else:
            loc = self.location(info.get("location"))
            instance = info.get("instance")
            delay = info.get("delay")
        return [loc, instance, delay]

    def before_set(self, character, new_location, instance):
        self.call("chat.channel-unjoin", character, self.call("chat.channel-info", "loc"))

    def lset(self, character, new_location, instance, delay):
        info = self.obj(DBCharacterLocation, character.uuid)
        info.set("location", new_location.uuid)
        if instance is None:
            info.delkey("instance")
        else:
            info.set("instance", instance)
        if delay is None:
            info.delkey("delay")
        else:
            info.set("delay", delay)
        info.store()

    def after_set(self, character, old_location, instance):
        self.call("chat.channel-join", character, self.call("chat.channel-info", "loc"))

    def ext_location(self):
        req = self.req()
        character = self.character(req.user())
        location = character.location
        if location is None:
            lst = self.objlist(DBLocationList, query_index="all")
            if len(lst):
                self.call("main-frame.error", '%s <a href="/admin#locations/config" target="_blank">%s</a>' % (self._("Starting location not configured."), self._("Open locations configuration")))
            else:
                self.call("main-frame.error", '%s <a href="/admin#locations/editor" target="_blank">%s</a>' % (self._("No locations defined."), self._("Open locations editor")))
        html = self.call("locations.render", location)
        if html is None:
            self.call("main-frame.error", self._("No visual image for location '%s'") % location.name)
        vars = {}
        self.call("game.response_internal", "location.html", vars, html)

    def gameinterface_render(self, character, vars, design):
        vars["js_modules"].add("locations")

    def ext_move(self):
        req = self.req()
        character = self.character(req.user())
        with self.lock(["CharacterLocation-%s" % character.uuid, "session.%s" % req.session().uuid]):
            if not character.tech_online:
                self.call("web.response_json", {"ok": False, "error": self._("Character offline")})
            if character.location_delay and character.location_delay > self.now():
                self.call("web.response_json", {"ok": False, "error": self._("You are busy"), "hide_title": True})
            old_location = character.location
            new_location = self.location(req.param("location"))
            if not new_location.valid():
                self.call("web.response_json", {"ok": False, "error": self._("No such location")})
            delay = 20
            character.set_location(new_location, character.instance, self.now(delay))
            self.call("web.response_json", {"ok": True, "name": new_location.name, "delay": delay})