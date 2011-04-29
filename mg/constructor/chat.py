from mg import *
from mg.constructor import *
import datetime
import re

re_chat_characters = re.compile(r'\[(chf|ch):([a-f0-9]{32})\]')
re_chat_command = re.compile(r'^\s*/(\S+)\s*(.*)')
re_loc_channel = re.compile(r'^loc-')
re_valid_command = re.compile(r'^/(\S+)$')

class Chat(ConstructorModule):
    def register(self):
        ConstructorModule.register(self)
        self.rhook("menu-admin-game.index", self.menu_game_index)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("headmenu-admin-chat.config", self.headmenu_chat_config)
        self.rhook("ext-admin-chat.config", self.chat_config, priv="chat.config")
        self.rhook("gameinterface.render", self.gameinterface_render)
        self.rhook("admin-gameinterface.design-files", self.gameinterface_advice_files)
        self.rhook("ext-chat.post", self.post, priv="logged")
        self.rhook("chat.message", self.message)

    def menu_game_index(self, menu):
        req = self.req()
        if req.has_access("chat.config"):
            menu.append({"id": "chat/config", "text": self._("Chat configuration"), "leaf": True, "order": 10})

    def permissions_list(self, perms):
        perms.append({"id": "chat.config", "name": self._("Chat configuration editor")})

    def headmenu_chat_config(self, args):
        return self._("Chat configuration")

    def chat_config(self):
        req = self.req()
        if req.param("ok"):
            config = self.app().config_updater()
            errors = {}
            location_separate = True if req.param("location-separate") else False
            config.set("chat.location-separate", location_separate)
            debug_channel = True if req.param("debug-channel") else False
            config.set("chat.debug-channel", debug_channel)
            trade_channel = True if req.param("trade-channel") else False
            config.set("chat.trade-channel", trade_channel)
            diplomacy_channel = True if req.param("diplomacy-channel") else False
            config.set("chat.diplomacy-channel", diplomacy_channel)
            # chatmode
            chatmode = intz(req.param("v_chatmode"))
            if chatmode < 0 or chatmode > 2:
                errors["chatmode"] = self._("Invalid selection")
            else:
                config.set("chat.channels-mode", chatmode)
            # channel selection commands
            if chatmode > 0:
                cmd_wld = req.param("cmd-wld")
                if cmd_wld != "":
                    m = re_valid_command.match(cmd_wld)
                    if m:
                        config.set("chat.cmd-wld", m.group(1))
                    else:
                        errors["cmd-wld"] = self._("Chat command must begin with / and must not contain non-whitespace characters")
                else:
                    config.set("chat.cmd-wld", "")
                cmd_loc = req.param("cmd-loc")
                if cmd_loc != "":
                    m = re_valid_command.match(cmd_loc)
                    if m:
                        config.set("chat.cmd-loc", m.group(1))
                    else:
                        errors["cmd-loc"] = self._("Chat command must begin with / and must not contain non-whitespace characters")
                else:
                    config.set("chat.cmd-loc", "")
                if trade_channel:
                    cmd_trd = req.param("cmd-trd")
                    if cmd_trd != "":
                        m = re_valid_command.match(cmd_trd)
                        if m:
                            config.set("chat.cmd-trd", m.group(1))
                        else:
                            errors["cmd-trd"] = self._("Chat command must begin with / and must not contain non-whitespace characters")
                    else:
                        config.set("chat.cmd-trd", "")
                if diplomacy_channel:
                    cmd_dip = req.param("cmd-dip")
                    if cmd_dip != "":
                        m = re_valid_command.match(cmd_dip)
                        if m:
                            config.set("chat.cmd-dip", m.group(1))
                        else:
                            errors["cmd-dip"] = self._("Chat command must begin with / and must not contain non-whitespace characters")
                    else:
                        config.set("chat.cmd-dip", "")
            # analysing errors
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            config.store()
            self.call("admin.response", self._("Chat configuration stored"), {})
        else:
            location_separate = self.conf("chat.location-separate")
            debug_channel = self.conf("chat.debug-channel")
            trade_channel = self.conf("chat.trade-channel")
            diplomacy_channel = self.conf("chat.diplomacy-channel")
            chatmode = self.chatmode()
            cmd_wld = self.cmd_wld()
            if cmd_wld != "":
                cmd_wld = "/%s" % cmd_wld
            cmd_loc = self.cmd_loc()
            if cmd_loc != "":
                cmd_loc = "/%s" % cmd_loc
            cmd_trd = self.cmd_trd()
            if cmd_trd != "":
                cmd_trd = "/%s" % cmd_trd
            cmd_dip = self.cmd_dip()
            if cmd_dip != "":
                cmd_dip = "/%s" % cmd_dip
        fields = [
            {"name": "chatmode", "label": self._("Chat channels mode"), "type": "combo", "value": chatmode, "values": [(0, self._("Channels disabled")), (1, self._("Every channel on a separate tab")), (2, self._("Channel selection checkboxes"))]},
            {"name": "location-separate", "type": "checkbox", "label": self._("Location chat is separated from the main channel"), "checked": location_separate, "condition": "[chatmode]>0"},
            {"name": "debug-channel", "type": "checkbox", "label": self._("Debugging channel enabled"), "checked": debug_channel, "condition": "[chatmode]>0"},
            {"name": "trade-channel", "type": "checkbox", "label": self._("Trading channel enabled"), "checked": trade_channel, "condition": "[chatmode]>0"},
            {"name": "diplomacy-channel", "type": "checkbox", "label": self._("Diplomacy channel enabled"), "checked": diplomacy_channel, "condition": "[chatmode]>0"},
            {"name": "cmd-wld", "label": self._("Chat command for writing to the entire world channel"), "value": cmd_wld, "condition": "[chatmode]>0"},
            {"name": "cmd-loc", "label": self._("Chat command for writing to the current location channel"), "value": cmd_loc, "condition": "[chatmode]>0"},
            {"name": "cmd-trd", "label": self._("Chat command for writing to the trading channel"), "value": cmd_trd, "condition": "[chatmode]>0 && [trade-channel]"},
            {"name": "cmd-dip", "label": self._("Chat command for writing to the trading channel"), "value": cmd_dip, "condition": "[chatmode]>0 && [diplomacy-channel]"},
        ]
        self.call("admin.form", fields=fields)

    def chatmode(self):
        return self.conf("chat.channels-mode", 1)

    def channels(self, chatmode):
        channels = []
        channels.append({
            "id": "main",
            "short_name": self._("channel///Main"),
            "switchable": True,
            "writable": True,
        })
        if chatmode:
            # channels enabled
            if self.conf("chat.location-separate"):
                channels.append({
                    "id": "loc",
                    "short_name": self._("channel///Location"),
                    "writable": True,
                    "switchable": True
                })
            else:
                channels[0]["writable"] = True
            if self.conf("chat.trade-channel"):
                channels.append({
                    "id": "trd",
                    "short_name": self._("channel///Trade"),
                    "switchable": True,
                    "writable": True
                })
            if self.conf("chat.diplomacy-channel"):
                channels.append({
                    "id": "dip",
                    "short_name": self._("channel///Diplomacy"),
                    "switchable": True,
                    "writable": True
                })
            if self.conf("chat.debug-channel"):
                channels.append({
                    "id": "dbg",
                    "short_name": self._("channel///Debug"),
                    "switchable": True,
                    "writable": True
                })
        else:
            channels[0]["writable"] = True
        return channels

    def gameinterface_render(self, vars, design):
        vars["js_modules"].add("chat")
        # list of channels
        chatmode = self.chatmode()
        channels = self.channels(chatmode)
        vars["js_init"].append("Chat.mode = %d;" % chatmode)
        if chatmode == 2:
            vars["js_init"].append("Chat.active_channel = 'main';")
        for ch in channels:
            vars["js_init"].append("Chat.channel_new({id: '%s', title: '%s'});" % (ch["id"], jsencode(ch["short_name"])))
        if chatmode and len(channels):
            vars["layout"]["chat_channels"] = True
            buttons = []
            state = None
            if chatmode == 1:
                for ch in channels:
                    buttons.append({
                        "id": ch["id"],
                        "state": "on" if ch["id"] == "main" else "off",
                        "onclick": "return Chat.tab_open('%s');" % ch["id"],
                        "hint": ch["short_name"]
                    })
            elif chatmode == 2:
                for ch in channels:
                    if ch.get("switchable"):
                        buttons.append({
                            "id": ch["id"],
                            "state": "on",
                            "onclick": "return Chat.channel_toggle('%s');" % ch["id"],
                            "hint": ch["short_name"]
                        })
            if len(buttons):
                for btn in buttons:
                    filename = "chat-%s" % btn["id"]
                    if design and (("%s-on.gif" % filename) in design.get("files")) and (("%s-off.gif" % filename) in design.get("files")):
                        btn["image"] = "%s/%s" % (design.get("uri"), filename)
                    else:
                        btn["image"] = "/st/game/chat/chat-channel"
                    vars["js_init"].append("Chat.button_images['%s'] = '%s';" % (btn["id"], btn["image"]))
                    btn["id"] = "chat-channel-button-%s" % btn["id"]
                buttons[-1]["lst"] = True
                vars["chat_buttons"] = buttons
        if chatmode == 1:
            vars["js_init"].append("Chat.tab_open('main');")
        vars["chat_channels"] = channels

    def gameinterface_advice_files(self, files):
        chatmode = self.chatmode()
        channels = self.channels(chatmode)
        if len(channels) >= 2:
            for ch in channels:
                if chatmode == 1 or ch.get("switchable"):
                    files.append({"filename": "chat-%s-off.gif" % ch["id"], "description": self._("Chat channel '%s' disabled") % ch["short_name"]})
                    files.append({"filename": "chat-%s-on.gif" % ch["id"], "description": self._("Chat channel '%s' enabled") % ch["short_name"]})

    def cmd_loc(self):
        return self.conf("chat.cmd-loc", "loc")

    def cmd_wld(self):
        return self.conf("chat.cmd-wld", "wld")

    def cmd_trd(self):
        return self.conf("chat.cmd-trd", "trd")

    def cmd_dip(self):
        return self.conf("chat.cmd-dip", "dip")

    def post(self):
        req = self.req()
        user = req.user()
        text = req.param("text") 
        channel = req.param("channel")
        if channel == "main" or channel == "":
            if self.conf("chat.location-separate"):
                channel = "wld"
            else:
                channel = "loc"
        # extracting commands
        while True:
            m = re_chat_command.match(text)
            if not m:
                break
            cmd, text = m.group(1, 2)
            if cmd == self.cmd_loc():
                channel = "loc"
            elif cmd == self.cmd_wld():
                channel = "wld"
            elif cmd == self.cmd_trd() and self.conf("chat.trade-channel"):
                channel = "trd"
            elif cmd == self.cmd_dip() and self.conf("chat.diplomacy-channel"):
                channel = "dip"
            else:
                self.call("web.response_json", {"error": self._("Unrecognized command: /%s") % htmlescape(cmd)})
        # access control
        if channel == "wld" or channel == "loc" or channel == "trd" and self.conf("chat.trade-channel") or channel == "dip" and self.conf("chat.diplomacy-channel"):
            pass
        else:
            self.call("web.response_json", {"error": self._("No access to the chat channel %s") % htmlescape(channel)})
        # translating channel name
        if channel == "loc":
            # TODO: convert to loc-%s format
            pass
        # sending message
        self.call("chat.message", html=u"[[chf:{0}]] {1}".format(user, htmlescape(text)), channel=channel)
        self.call("web.response_json", {"ok": True, "channel": self.channel2tab(channel)})

    def message(self, **kwargs):
        try:
            req = self.req()
        except AttributeError:
            req = None
        html = kwargs.get("html")
        # replacing character tags [chf:UUID], [ch:UUID] etc
        tokens = []
        start = 0
        for match in re_chat_characters.finditer(html):
            match_start, match_end = match.span()
            if match_start > start:
                tokens.append(html[start:match_start])
            start = match_end
            tp, character = match.group(1, 2)
            character = self.character(character)
            if tp == "chf":
                tokens.append(u'<span class="chat-msg-from">%s</span>' % htmlescape(character.name))
            elif tp == "ch":
                tokens.append(u'<span class="chat-msg-char">%s</span>' % htmlescape(character.name))
        if len(html) > start:
            tokens.append(html[start:])
        html = u"".join(tokens)
        # formatting html
        html = u'<span class="chat-msg-body">%s</span>' % html
        # time
        if not kwargs.get("hide_time"):
            now = datetime.datetime.utcnow().strftime("%H:%M:%S")
            html = u'<span class="chat-msg-time">%s</span> %s' % (now, html)
        kwargs["html"] = html
        # channel
        channel = kwargs.get("channel")
        if not channel:
            channel = "sys"
        # store chat message
        # TODO
        # translate channel name
        kwargs["channel"] = self.channel2tab(channel)
        # sending message
        self.call("stream.packet", "global", "chat", "msg", **kwargs)

    def channel2tab(self, channel):
        if channel == "sys" or channel == "wld" or channel == "loc" and not self.conf("chat.location-separate"):
            return "main"
        if re_loc_channel.match(channel):
            if self.conf("chat.location-separate"):
                return "loc"
            else:
                return "main"
        return channel
