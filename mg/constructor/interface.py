from mg import *
from mg.constructor.design import Design
from mg.core.auth import User
from mg.constructor.players import Player, Character, CharacterList
import re
import hashlib
import mg

caching = False

class Dynamic(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-dyn-mg.indexpage.js", self.indexpage_js)
        self.rhook("ext-dyn-mg.indexpage.css", self.indexpage_css)
        self.rhook("auth.char-form-changed", self.char_form_changed)
        self.rhook("ext-dyn-mg.game.js", self.game_js)
        self.rhook("ext-dyn-mg.game.css", self.game_css)
        self.rhook("gameinterface.layout-changed", self.layout_changed)

    def indexpage_js_mcid(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        ver = self.int_app().config.get("application.version", 0)
        return "indexpage-js-%s-%s-%s" % (main_host, lang, ver)

    def char_form_changed(self):
        for mcid in [self.indexpage_js_mcid(), self.indexpage_css_mcid()]:
            self.app().mc.delete(mcid)

    def indexpage_js(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        mcid = self.indexpage_js_mcid()
        data = self.app().mc.get(mcid)
        if not data or not caching:
            mg_path = mg.__path__[0]
            vars = {
                "includes": [
                    "%s/../static/js/prototype.js" % mg_path,
                    "%s/../static/js/gettext.js" % mg_path,
                    "%s/../static/constructor/gettext-%s.js" % (mg_path, lang),
                ],
                "main_host": main_host
            }
            self.call("indexpage.render", vars)
            data = self.call("web.parse_template", "constructor/index/indexpage.js", vars)
            self.app().mc.set(mcid, data)
        self.call("web.response", data, "text/javascript; charset=utf-8")

    def indexpage_css_mcid(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        ver = self.int_app().config.get("application.version", 0)
        return "indexpage-css-%s-%s-%s" % (main_host, lang, ver)

    def indexpage_css(self):
        main_host = self.app().inst.config["main_host"]
        mcid = self.indexpage_css_mcid()
        data = self.app().mc.get(mcid)
        if not data or not caching:
            mg_path = mg.__path__[0]
            vars = {
                "main_host": main_host
            }
            data = self.call("web.parse_template", "constructor/index/indexpage.css", vars)
            self.app().mc.set(mcid, data)
        self.call("web.response", data, "text/css")

    def layout_changed(self):
        for mcid in [self.game_js_mcid(), self.game_css_mcid()]:
            self.app().mc.delete(mcid)

    def game_js_mcid(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        ver = self.int_app().config.get("application.version", 0)
        return "game-js-%s-%s-%s" % (main_host, lang, ver)

    def game_css_mcid(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        ver = self.int_app().config.get("application.version", 0)
        return "game-css-%s-%s-%s" % (main_host, lang, ver)

    def game_css(self):
        main_host = self.app().inst.config["main_host"]
        mcid = self.game_css_mcid()
        data = self.app().mc.get(mcid)
        if not data or not caching:
            mg_path = mg.__path__[0]
            vars = {
                "main_host": main_host
            }
            data = self.call("web.parse_template", "game/main.css", vars)
            self.app().mc.set(mcid, data)
        self.call("web.response", data, "text/css")

    def game_js(self):
        main_host = self.app().inst.config["main_host"]
        lang = self.call("l10n.lang")
        mcid = self.game_js_mcid()
        data = self.app().mc.get(mcid)
        if not data or not caching:
            mg_path = mg.__path__[0]
            vars = {
                "main_host": main_host,
                "layout": {
                    "scheme": self.conf("gameinterface.layout-scheme", 1),
                    "chatmode": self.conf("gameinterface.chat-mode", 1),
                    "marginleft": self.conf("gameinterface.margin-left", 0),
                    "marginright": self.conf("gameinterface.margin-right", 0),
                    "margintop": self.conf("gameinterface.margin-top", 0),
                    "marginbottom": self.conf("gameinterface.margin-bottom", 0),
                },
            }
            channels = []
            self.call("chat.channels", channels)
            channels_res = []
            for ch in channels:
                channels_res.append({
                    "id": ch["id"],
                    "short_name": htmlescape(ch["short_name"])
                })
            vars["chat_channels"] = channels_res
            self.call("gameinterface.render", vars)
            data = self.call("web.parse_template", "game/interface.js", vars)
            self.app().mc.set(mcid, data)
        self.call("web.response", data, "text/javascript; charset=utf-8")

class Interface(Module):
    def register(self):
        Module.register(self)
        self.rhook("ext-index.index", self.index)
        self.rhook("indexpage.error", self.index_error)
        self.rhook("indexpage.response_template", self.response_template)
        self.rhook("auth.messages", self.auth_messages)
        self.rhook("menu-admin-design.index", self.menu_design_index)
        self.rhook("ext-admin-gameinterface.layout", self.gameinterface_layout)

    def auth_messages(self, msg):
        msg["name_unknown"] = self._("Character not found")
        msg["user_inactive"] = self._("Character is not active. Check your e-mail and follow activation link")

    def index(self):
        req = self.req()
        session_param = req.param("session")
        if session_param:
            session = self.call("session.get")
            if session.uuid != session_param:
                self.call("web.redirect", "/")
            user = session.get("user")
            if not user:
                self.call("web.redirect", "/")
            character = self.obj(Character, user)
            player = self.obj(Player, character.get("player"))
            if self.conf("auth.multicharing") or self.conf("auth.cabinet"):
                return self.game_cabinet(player)
            else:
                return self.game_interface_default_character(player)

        email = req.param("email")
        if email:
            user = self.call("session.find_user", email)
            if user:
                password = req.param("password")
                m = hashlib.md5()
                m.update(user.get("salt").encode("utf-8") + password.encode("utf-8"))
                if m.hexdigest() == user.get("pass_hash"):
                    self.call("web.response", "ENTERING GAME", {})
        interface = self.conf("indexpage.design")
        if not interface:
            return self.call("indexpage.error", self._("Index page design is not configured"))
        design = self.obj(Design, interface)
        project = self.app().project
        author_name = self.conf("gameprofile.author_name")
        if not author_name:
            owner = self.main_app().obj(User, project.get("owner"))
            author_name = owner.get("name")
        vars = {
            "title": htmlescape(project.get("title_full")),
            "game": {
                "title_full": htmlescape(project.get("title_full")),
                "title_short": htmlescape(project.get("title_short")),
                "description": self.call("socio.format_text", self.conf("gameprofile.description")),
            },
            "htmlmeta": {
                "description": htmlescape(self.conf("gameprofile.indexpage_description")),
                "keywords": htmlescape(self.conf("gameprofile.indexpage_keywords")),
            },
            "year": re.sub(r'-.*', '', self.now()),
            "copyright": "Joy Team, %s" % htmlescape(author_name),
        }
        links = []
        self.call("indexpage.links", links)
        if len(links):
            links.sort(cmp=lambda x, y: cmp(x.get("order"), y.get("order")))
            links[-1]["lst"] = True
            vars["links"] = links
        self.call("design.response", design, "index.html", "", vars)

    def index_error(self, msg):
        vars = {
            "title": self._("Error"),
            "msg": msg,
        }
        self.call("indexpage.response_template", "constructor/index/error.html", vars)

    def response_template(self, template, vars):
        content = self.call("web.parse_template", template, vars)
        self.call("web.response_global", content, vars)

    def game_cabinet(self, player):
        self.index_error("The cabinet is not implemented yet")

    def game_interface_default_character(self, player):
        chars = self.objlist(CharacterList, query_index="player", query_equal=player.uuid, query_reversed=True, query_limit=1)
        if not len(chars):
            self.call("web.redirect", "/character/create")
        chars.load()
        return self.game_interface(chars[0])

    def game_interface(self, character):
        project = self.app().project
        vars = {
            "title": htmlescape(project.get("title_full")),
            "global_html": "game/frameset.html"
        }
        self.call("web.response_global", "", vars)

    def menu_design_index(self, menu):
        req = self.req()
        if req.has_access("design"):
            menu.append({"id": "gameinterface/layout", "text": self._("Game interface layout"), "leaf": True, "order": 2})

    def gameinterface_layout(self):
        self.call("session.require_permission", "design")
        req = self.req()
        if req.ok():
            config = self.app().config
            errors = {}
            # scheme
            scheme = intz(req.param("scheme"))
            if scheme < 1 or scheme > 3:
                errors["scheme"] = self._("Invalid selection")
            else:
                config.set("gameinterface.layout-scheme", scheme)
            # chatmode
            chatmode = intz(req.param("v_chatmode"))
            if chatmode < 0 or chatmode > 2:
                errors["chatmode"] = self._("Invalid selection")
            else:
                config.set("gameinterface.chat-mode", chatmode)
            # margin-left
            marginleft = req.param("marginleft")
            if not valid_nonnegative_int(marginleft):
                errors["marginleft"] = self._("Enter width in pixels")
            else:
                config.set("gameinterface.margin-left", marginleft)
            # margin-right
            marginright = req.param("marginright")
            if not valid_nonnegative_int(marginright):
                errors["marginright"] = self._("Enter width in pixels")
            else:
                config.set("gameinterface.margin-right", marginright)
            # margin-top
            margintop = req.param("margintop")
            if not valid_nonnegative_int(margintop):
                errors["margintop"] = self._("Enter width in pixels")
            else:
                config.set("gameinterface.margin-top", margintop)
            # margin-bottom
            marginbottom = req.param("marginbottom")
            if not valid_nonnegative_int(marginbottom):
                errors["marginbottom"] = self._("Enter width in pixels")
            else:
                config.set("gameinterface.margin-bottom", marginbottom)
            # analysing errors
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("gameinterface.layout-changed")
            self.call("admin.response", self._("Settings stored"), {})
        else:
            scheme = self.conf("gameinterface.layout-scheme", 1)
            chatmode = self.conf("gameinterface.chat-mode", 1)
            marginleft = self.conf("gameinterface.margin-left", 0)
            marginright = self.conf("gameinterface.margin-right", 0)
            margintop = self.conf("gameinterface.margin-top", 0)
            marginbottom = self.conf("gameinterface.margin-bottom", 0)
        fields = [
            {"id": "scheme0", "name": "scheme", "type": "radio", "label": self._("General layout scheme"), "value": 1, "checked": scheme == 1, "boxLabel": '<img src="/st/constructor/gameinterface/layout0.png" alt="" />' },
            {"id": "scheme1", "name": "scheme", "type": "radio", "label": "&nbsp;", "value": 2, "checked": scheme == 2, "boxLabel": '<img src="/st/constructor/gameinterface/layout1.png" alt="" />', "inline": True},
            {"id": "scheme2", "name": "scheme", "type": "radio", "label": "&nbsp;", "value": 3, "checked": scheme == 3, "boxLabel": '<img src="/st/constructor/gameinterface/layout2.png" alt="" />', "inline": True},
            {"type": "label", "label": self._("Page margins (0 - margin is disabled):")},
            {"type": "html", "html": '<img src="/st/constructor/gameinterface/margins.png" style="margin: 3px 0 5px 0" />'},
            {"name": "marginleft", "label": self._("Left"), "value": marginleft},
            {"name": "marginright", "label": self._("Right"), "value": marginright, "inline": True},
            {"name": "margintop", "label": self._("Top"), "value": margintop, "inline": True},
            {"name": "marginbottom", "label": self._("Bottom"), "value": marginbottom, "inline": True},
            {"name": "chatmode", "label": self._("Chat channels mode"), "type": "combo", "value": chatmode, "values": [(0, self._("Channels disabled")), (1, self._("Every channel on a separate tab")), (2, self._("Channel selection checkboxes"))]},
        ]
        self.call("admin.form", fields=fields)

