from mg.constructor import *
from mg.mmorpg.crafting_classes import *
import mg
from uuid import uuid4
from PIL import Image
import cStringIO

re_del = re.compile(r'^del/(.+)$')
re_recipes_cmd = re.compile(r'^(view|ingredients|production)/([0-9a-f]+)(?:|/(.+))$')
re_truncate = re.compile(r'^(.{17}).{3}.+$', re.DOTALL)

class Crafting(ConstructorModule):
    def register(self):
        self.rhook("crafting.categories", self.categories)
        self.rhook("interfaces.list", self.interfaces_list)
        self.rhook("gameinterface.buttons", self.gameinterface_buttons)
        self.rhook("interface-crafting.action-default", self.interface_crafting, priv="logged")

    def child_modules(self):
        return ["mg.mmorpg.crafting.CraftingAdmin"]

    def categories(self):
        categories = self.conf("crafting.categories")
        if categories is not None:
            return categories
        return [
            {
                "id": "potions",
                "name": self._("Potions"),
                "order": 10.0,
            },
            {
                "id": "elixirs",
                "name": self._("Elixirs"),
                "order": 20.0,
            },
        ]

    def interfaces_list(self, types):
        types.append(("crafting", self._("Crafting")))

    def gameinterface_buttons(self, buttons):
        funcs = self.call("globfunc.functions")
        for func in funcs:
            if func["tp"] == "crafting":
                buttons.append({
                    "id": func["id"],
                    "href": "/globfunc/%s" % func["id"],
                    "target": "main",
                    "icon": "crafting.png",
                    "title": self._("Crafting"),
                    "block": "left-menu",
                    "order": 4,
                })

    def interface_crafting(self, func_id, base_url, func, args, vars):
        req = self.req()
        if req.ok():
            lock_objects = []
            if req.ok():
                lock_objects.append(character.lock)
                lock_objects.append(character.inventory.lock_key)
            with self.lock(lock_objects):
                character.inventory.load()
        enabled_recipes = func.get("crafting_recipes", {})
        recipes = self.objlist(DBCraftingRecipeList, enabled_recipes.keys())
        recipes.load(silent=True)
        categories = self.call("crafting.categories")
        rcategories = []
        for cat in categories:
            rrecipes = []
            for rcp in recipes:
                if rcp.get("category") == cat["id"]:
                    rrecipe = {
                        "id": rcp.uuid,
                        "name": htmlescape(rcp.get("name")),
                        "image": rcp.get("image"),
                        "params": None,
                        "description": rcp.get("description"),
                    }
                    rrecipes.append(rrecipe)
            if rrecipes:
                rcategories.append({
                    "id": cat["id"],
                    "name_html_js": jsencode(htmlescape(cat.get("name"))),
                    "visible": func.get("default_category") == cat["id"],
                    "recipes": rrecipes,
                })
        vars["categories"] = rcategories
        content = self.call("game.parse_internal", func.get("shop_template", "crafting-recipes-layout.html"), vars)
        content = self.call("game.parse_internal", "crafting-recipes.html", vars, content)
        self.call("game.response_internal", "crafting-global.html", vars, content)

class CraftingAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-peaceful.index", self.menu_peaceful_index)
        self.rhook("menu-admin-crafting.index", self.menu_crafting_index)
        self.rhook("ext-admin-crafting.categories", self.admin_categories, priv="peaceful.crafting")
        self.rhook("headmenu-admin-crafting.categories", self.headmenu_categories)
        self.rhook("ext-admin-crafting.recipes", self.admin_recipes, priv="peaceful.crafting")
        self.rhook("headmenu-admin-crafting.recipes", self.headmenu_recipes)
        self.rhook("admin-globfunc.predefined", self.globfuncs)
        self.rhook("admin-interfaces.form", self.form_render)
        self.rhook("admin-interface-crafting.store", self.form_store)

    def globfuncs(self, funcs):
        funcs.append({
            "id": "u_crafting",
            "type": "crafting",
            "title": self._("Crafting"),
            "tp": "crafting",
        })

    def permissions_list(self, perms):
        perms.append({"id": "peaceful.crafting", "name": self._("Peaceful activities: crafting")})

    def menu_peaceful_index(self, menu):
        menu.append({"id": "crafting.index", "text": self._("Crafting"), "order": 10})

    def menu_crafting_index(self, menu):
        req = self.req()
        if req.has_access("peaceful.crafting"):
            menu.append({"id": "crafting/categories", "text": self._("Recipes categories"), "order": 0, "leaf": True})
            menu.append({"id": "crafting/recipes", "text": self._("Recipes"), "order": 10, "leaf": True})

    def headmenu_categories(self, args):
        if args == "new":
            return [self._("New category"), "crafting/categories"]
        elif args:
            for cat in self.call("crafting.categories"):
                if cat["id"] == args:
                    return [htmlescape(cat.get("name")), "crafting/categories"]
        return self._("Crafting recipes categories")

    def admin_categories(self):
        categories = self.call("crafting.categories")
        req = self.req()
        m = re_del.match(req.args)
        if m:
            catid = m.group(1)
            categories = [cat for cat in categories if cat["id"] != catid]
            config = self.app().config_updater()
            config.set("crafting.categories", categories)
            config.store()
            self.call("admin.redirect", "crafting/categories")
        if req.args:
            if req.args == "new":
                cat = {
                    "id": uuid4().hex
                }
                order = None
                for c in categories:
                    if order is None or c["order"] > order:
                        order = c["order"]
                if order is None:
                    cat["order"] = 0.0
                else:
                    cat["order"] = order + 10.0
            else:
                cat = None
                for c in categories:
                    if c["id"] == req.args:
                        cat = c
                        break
                if cat is None:
                    self.call("admin.redirect", "crafting/categories")
            if req.ok():
                cat = cat.copy()
                errors = {}
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    cat["name"] = name
                # order
                cat["order"] = floatz(req.param("order"))
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # save
                categories = [c for c in categories if c["id"] != cat["id"]]
                categories.append(cat)
                categories.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["name"], y["name"]))
                config = self.app().config_updater()
                config.set("crafting.categories", categories)
                config.store()
                self.call("admin.redirect", "crafting/categories")
            fields = [
                {"name": "name", "label": self._("Category name"), "value": cat.get("name")},
                {"name": "order", "label": self._("Sorting order"), "value": cat.get("order"), "inline": True},
            ]
            self.call("admin.form", fields=fields)
        rows = []
        for cat in categories:
            rows.append([
                htmlescape(cat.get("name")),
                cat.get("order"),
                u'<hook:admin.link href="crafting/categories/%s" title="%s" />' % (cat["id"], self._("edit")),
                u'<hook:admin.link href="crafting/categories/del/%s" title="%s" confirm="%s" />' % (cat["id"], self._("delete"), self._("Are you sure want to delete this category?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "crafting/categories/new",
                            "text": self._("New category"),
                            "lst": True,
                        },
                    ],
                    "header": [
                        self._("Category name"),
                        self._("Sorting order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                },
            ],
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def load_recipes(self):
        req = self.req()
        try:
            return req._crafting_recipes
        except AttributeError:
            lst = self.objlist(DBCraftingRecipeList, query_index="all")
            lst.load(silent=True)
            recipes = sorted(lst, cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)))
            req._crafting_recipes = recipes
            return recipes

    def load_recipe(self, uuid):
        try:
            return self.obj(DBCraftingRecipe, uuid)
        except ObjectNotFoundException:
            return None

    def headmenu_recipes(self, args):
        m = re_recipes_cmd.match(args)
        if m:
            cmd, recipe_id, args = m.group(1, 2, 3)
            rcp = self.load_recipe(recipe_id)
            if rcp:
                if cmd == "view":
                    return [htmlescape(rcp.get("name")), "crafting/recipes"]
                elif cmd == "ingredients":
                    if args == "new":
                        return [self._("New ingredient"), "crafting/recipes/view/%s" % recipe_id]
                    elif args:
                        for ing in rcp.get("ingredients", []):
                            if ing["id"] == args:
                                item_type = self.item_type(ing["item_type"])
                                return [self._("Ingredient '%s'") % htmlescape(item_type.name), "crafting/recipes/view/%s" % recipe_id]
                elif cmd == "production":
                    if args == "new":
                        return [self._("New product"), "crafting/recipes/view/%s" % recipe_id]
                    elif args:
                        for ing in rcp.get("production", []):
                            if ing["id"] == args:
                                item_type = self.item_type(ing["item_type"])
                                return [self._("Product '%s'") % htmlescape(item_type.name), "crafting/recipes/view/%s" % recipe_id]
        elif args == "new":
            return [self._("New recipe"), "crafting/recipes"]
        elif args:
            rcp = self.load_recipe(args)
            if rcp:
                return [self._("Editing"), "crafting/recipes/view/%s" % args]
        return self._("Crafting recipes")

    def admin_recipes(self):
        categories = self.call("crafting.categories")
        req = self.req()
        m = re_recipes_cmd.match(req.args)
        if m:
            cmd, recipe_id, args = m.group(1, 2, 3)
            recipe = self.load_recipe(recipe_id)
            if recipe:
                if cmd == "view":
                    return self.admin_recipe_view(recipe, args)
                if cmd == "ingredients":
                    return self.admin_recipe_ingredients(recipe, args)
                if cmd == "production":
                    return self.admin_recipe_production(recipe, args)
            self.call("admin.redirect", "crafting/recipes")
        m = re_del.match(req.args)
        if m:
            rcpid = m.group(1)
            rcp = self.load_recipe(rcpid)
            if rcp:
                if rcp.get("image"):
                    self.call("cluster.static_delete", rcp.get("image"))
                rcp.remove()
            self.call("admin.redirect", "crafting/recipes")
        if req.args:
            if req.args == "new":
                rcp = self.obj(DBCraftingRecipe)
                recipes = self.load_recipes()
                rcp.set("order", recipes[-1].get("order") + 10.0 if recipes else 0.0)
            else:
                rcp = self.load_recipe(req.args)
                if not rcp:
                    self.call("admin.redirect", "crafting/recipes")
            # prepare list of categories
            valid_categories = set()
            categories_values = [(None, self._("Select a category"))]
            for cat in categories:
                valid_categories.add(cat["id"])
                categories_values.append((cat["id"], cat["name"]))
            if req.ok():
                self.call("web.upload_handler")
                errors = {}
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    rcp.set("name", name)
                # order
                rcp.set("order", floatz(req.param("order")))
                # category
                category = req.param("v_category")
                if category not in valid_categories:
                    errors["v_category"] = self._("Select valid category")
                else:
                    rcp.set("category", category)
                # image
                old_image = rcp.get("image")
                image_data = req.param_raw("image")
                if image_data:
                    try:
                        image = Image.open(cStringIO.StringIO(image_data))
                        if image.load() is None:
                            raise IOError
                    except IOError:
                        errors["image"] = self._("Image format not recognized")
                    else:
                        ext, content_type = self.image_format(image)
                        form = image.format
                        if ext is None:
                            errors["image"] = self._("Valid formats are: PNG, GIF, JPEG")
                        else:
                            w, h = image.size
                            if h != 100:
                                w = w * 100 / h
                                h = 100
                            if w < 100:
                                h = h * 100 / w
                                w = 100
                            left = (w - 100) / 2
                            top = (h - 100) / 2
                            image = image.resize((w, h), Image.ANTIALIAS).crop((left, top, left + 100, top + 100))
                # process errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # upload image
                if image_data:
                    data = cStringIO.StringIO()
                    if form == "JPEG":
                        image.save(data, form, quality=95)
                    else:
                        image.save(data, form)
                    rcp.set("image", self.call("cluster.static_upload", "recipe", ext, content_type, data.getvalue()))
                # save
                rcp.store()
                # delete old image
                if image_data and old_image:
                    self.call("cluster.static_delete", old_image)
                self.call("admin.redirect", "crafting/recipes/view/%s" % rcp.uuid)
            fields = [
                {"name": "name", "label": self._("Recipe name"), "value": rcp.get("name")},
                {"name": "order", "label": self._("Sorting order"), "value": rcp.get("order"), "inline": True},
                {"name": "category", "label": self._("Category"), "type": "combo", "value": rcp.get("category"), "values": categories_values},
                {"name": "image", "type": "fileuploadfield", "label": self._("Recipe image")},
            ]
            self.call("admin.form", fields=fields, modules=["FileUploadField"])
        if not categories:
            self.call("admin.response", u'<div class="admin-alert">%s</div>' % (self._("Before creating recipes go to the '{href}' page first and create one or more categories").format(href=u'<hook:admin.link href="crafting/categories" title="%s" />' % self._("Recipes categories"))), {})
        tables = [
            {
                "links": [
                    {
                        "hook": "crafting/recipes/new",
                        "text": self._("New recipe"),
                        "lst": True,
                    },
                ],
            }
        ]
        displayed_recipes = set()
        header = [
            self._("Recipe name"),
            self._("Sorting order"),
            self._("Editing"),
            self._("Deletion"),
        ]
        recipes = self.load_recipes()
        for cat in categories:
            rows = []
            for rcp in recipes:
                if rcp.get("category") == cat["id"]:
                    rows.append([
                        htmlescape(rcp.get("name")),
                        rcp.get("order"),
                        u'<hook:admin.link href="crafting/recipes/view/%s" title="%s" />' % (rcp.uuid, self._("open")),
                        u'<hook:admin.link href="crafting/recipes/del/%s" title="%s" confirm="%s" />' % (rcp.uuid, self._("delete"), self._("Are you sure want to delete this recipe?")),
                    ])
                    displayed_recipes.add(rcp.uuid)
            if rows:
                tables.append({
                    "title": htmlescape(cat["name"]),
                    "header": header,
                    "rows": rows,
                })
        rows = []
        for rcp in recipes:
            if rcp.uuid not in displayed_recipes:
                rows.append([
                    htmlescape(rcp.get("name")),
                    rcp.get("order"),
                    u'<hook:admin.link href="crafting/recipes/view/%s" title="%s" />' % (rcp.uuid, self._("open")),
                    u'<hook:admin.link href="crafting/recipes/del/%s" title="%s" confirm="%s" />' % (rcp.uuid, self._("delete"), self._("Are you sure want to delete this recipe?")),
                ])
        if rows:
            tables.append({
                "title": self._("Uncategorized"),
                "header": header,
                "rows": rows,
            })
        vars = {
            "tables": tables
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def form_render(self, fields, func):
        categories = self.call("crafting.categories")
        recipes = self.load_recipes()
        fields.append({
            "name": "default_category",
            "type": "combo",
            "label": self._("Open this category by default"),
            "value": func.get("default_category"),
            "values": [(cat["id"], cat["name"]) for cat in categories],
        })
        enabled_recipes = func.get("crafting_recipes", {})
        for cat in categories:
            first_recipe = True
            col = 0
            cols = 3
            for rcp in recipes:
                if rcp.get("category") == cat["id"]:
                    if first_recipe:
                        fields.append({
                            "type": "header",
                            "html": self._("Available recipes: %s") % htmlescape(cat["name"]),
                            "condition": "[tp] == 'crafting'",
                        })
                        first_recipe = False
                    fields.append({
                        "type": "checkbox",
                        "name": "crafting_%s" % rcp.uuid,
                        "checked": enabled_recipes.get(rcp.uuid),
                        "label": htmlescape(rcp.get("name")),
                        "condition": "[tp] == 'crafting'",
                        "inline": col != 0,
                    })
                    col = (col + 1) % cols
            while col:
                fields.append({
                    "type": "empty",
                    "condition": "[tp] == 'crafting'",
                    "inline": col != 0,
                })
                col = (col + 1) % cols

    def form_store(self, func, errors):
        req = self.req()
        categories = self.call("crafting.categories")
        recipes = self.load_recipes()
        used_categories = set()
        if "crafting_recipes" not in func:
            func["crafting_recipes"] = {}
        enabled_recipes = func["crafting_recipes"]
        for cat in categories:
            for rcp in recipes:
                if rcp.get("category") == cat["id"]:
                    if req.param("crafting_%s" % rcp.uuid):
                        enabled_recipes[rcp.uuid] = True
                        used_categories.add(cat["id"])
                    elif enabled_recipes.get(rcp.uuid):
                        del enabled_recipes[rcp.uuid]
        default_category = req.param("v_default_category")
        if not used_categories:
            self.call("web.response_json", {"success": False, "errormsg": self._("No recipes selected")})
        elif default_category not in used_categories:
            errors["v_default_category"] = self._("Select a category which contains at least 1 enabled recipe")
        else:
            func["default_category"] = default_category

    def admin_recipe_view(self, recipe, args):
        ingredients = []
        for ing in recipe.get("ingredients", []):
            item_type = self.item_type(ing.get("item_type"))
            quantity = self.call("script.unparse-expression", ing.get("quantity"))
            quantity = re_truncate.sub(r'\1...', quantity)
            requirements = []
            if ing.get("equipped"):
                requirements.append(self._("item///must be equipped"))
            ingredients.append([
                htmlescape(item_type.name),
                htmlescape(quantity),
                '<div class="nowrap">%s</div>' % ('<br />'.join(requirements)),
                ing.get("order"),
                u'<hook:admin.link href="crafting/recipes/ingredients/%s/%s" title="%s" />' % (recipe.uuid, ing["id"], self._("edit")),
                u'<hook:admin.link href="crafting/recipes/ingredients/%s/del/%s" title="%s" confirm="%s" />' % (recipe.uuid, ing["id"], self._("delete"), self._("Are you sure want to delete this ingredient?")),
            ])
        production = []
        for prod in recipe.get("production", []):
            item_type = self.item_type(prod.get("item_type"))
            quantity = self.call("script.unparse-expression", prod.get("quantity"))
            quantity = re_truncate.sub(r'\1...', quantity)
            mods = []
            for key in sorted(prod.get("mods", {}).keys()):
                line = u"%s = %s" % (key, self.call("script.unparse-expression", prod["mods"][key]))
                line = re_truncate.sub(r'\1...', line)
                mods.append(line)
            production.append([
                htmlescape(item_type.name),
                htmlescape(quantity),
                '<div class="nowrap">%s</div>' % ('<br />'.join(mods)),
                prod.get("order"),
                u'<hook:admin.link href="crafting/recipes/production/%s/%s" title="%s" />' % (recipe.uuid, prod["id"], self._("edit")),
                u'<hook:admin.link href="crafting/recipes/production/%s/del/%s" title="%s" confirm="%s" />' % (recipe.uuid, prod["id"], self._("delete"), self._("Are you sure want to delete this product?")),
            ])
        params = [
            [self._("recipe///Name"), htmlescape(recipe.get("name"))],
            [self._("Sorting order"), recipe.get("order")],
        ]
        if recipe.get("image"):
            params.append([self._("Recipe image"), '<img src="%s" alt="" />' % recipe.get("image")])
        vars = {
            "tables": [
                {
                    "links": [
                        {
                            "hook": "crafting/recipes/%s" % recipe.uuid,
                            "text": self._("Edit recipe parameters"),
                            "lst": True,
                        },
                    ],
                    "rows": params,
                },
                {
                    "title": self._("Ingredients"),
                    "links": [
                        {
                            "hook": "crafting/recipes/ingredients/%s/new" % recipe.uuid,
                            "text": self._("New ingredient"),
                            "lst": True,
                        },
                    ],
                    "header": [
                        self._("Item name"),
                        self._("Quantity (in fractions of items)"),
                        self._("Special requirements"),
                        self._("Sorting order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": ingredients,
                },
                {
                    "title": self._("Production"),
                    "links": [
                        {
                            "hook": "crafting/recipes/production/%s/new" % recipe.uuid,
                            "text": self._("New product"),
                            "lst": True,
                        },
                    ],
                    "header": [
                        self._("Item name"),
                        self._("Quantity (in whole items)"),
                        self._("Modifications"),
                        self._("Sorting order"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": production,
                },
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def load_item_types(self):
        categories = self.call("item-types.categories", "admin")
        item_types = self.call("item-types.list")
        valid_item_types = set()
        item_type_values = []
        item_type_values.append((None, None))
        for cat in categories:
            first_item_type = True
            for item_type in item_types:
                if item_type.get("cat-admin") == cat["id"]:
                    if first_item_type:
                        item_type_values.append((None, cat["name"]))
                        first_item_type = False
                    item_type_values.append((item_type.uuid, u"----- %s" % item_type.get("name")))
                    valid_item_types.add(item_type.uuid)
        return item_type_values, valid_item_types

    def admin_recipe_ingredients(self, recipe, args):
        req = self.req()
        item_type_values, valid_item_types = self.load_item_types()
        ingredients = recipe.get("ingredients", [])
        m = re_del.match(args)
        if m:
            uuid = m.group(1)
            ingredients = [i for i in ingredients if i["id"] != uuid]
            recipe.set("ingredients", ingredients)
            recipe.touch()
            recipe.store()
            self.call("admin.redirect", "crafting/recipes/view/%s" % recipe.uuid)
        if args == "new":
            ing = {
                "id": uuid4().hex,
                "order": ingredients[-1]["order"] + 10.0 if ingredients else 0.0,
            }
        else:
            for i in ingredients:
                if i["id"] == args:
                    ing = i.copy()
                    break
            if ing is None:
                self.call("admin.redirect", "crafting/recipes/view/%s" % recipe.uuid)
        if req.ok():
            errors = {}
            # item_type
            item_type = req.param("v_item_type")
            if not item_type:
                errors["v_item_type"] = self._("This field is mandatory")
            elif item_type not in valid_item_types:
                errors["v_item_type"] = self._("Make a valid selection")
            else:
                ing["item_type"] = item_type
            # order
            ing["order"] = floatz(req.param("order"))
            # quantity
            char = self.character(req.user())
            ing["quantity"] = self.call("script.admin-expression", "quantity", errors, globs={"char": char})
            # equipped
            ing["equipped"] = True if req.param("equipped") else False
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # save
            ingredients = [i for i in ingredients if i["id"] != ing["id"]]
            ingredients.append(ing)
            ingredients.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            recipe.set("ingredients", ingredients)
            recipe.touch()
            recipe.store()
            self.call("admin.redirect", "crafting/recipes/view/%s" % recipe.uuid)
        fields = [
            {"name": "item_type", "label": self._("Item type"), "type": "combo", "values": item_type_values, "value": ing.get("item_type")},
            {"name": "order", "label": self._("Sorting order"), "value": ing.get("order"), "inline": True},
            {"name": "quantity", "label": self._("Quantity of fractions to take") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", ing.get("quantity", 1))},
            {"name": "equipped", "label": self._("Item must be equipped"), "type": "checkbox", "checked": ing.get("equipped")},
        ]
        self.call("admin.form", fields=fields)

    def admin_recipe_production(self, recipe, args):
        req = self.req()
        item_type_values, valid_item_types = self.load_item_types()
        params = self.call("item-types.params")
        production = recipe.get("production", [])
        m = re_del.match(args)
        if m:
            uuid = m.group(1)
            production = [p for p in production if p["id"] != uuid]
            recipe.set("production", production)
            recipe.touch()
            recipe.store()
            self.call("admin.redirect", "crafting/recipes/view/%s" % recipe.uuid)
        if args == "new":
            prod = {
                "id": uuid4().hex,
                "order": production[-1]["order"] + 10.0 if production else 0.0,
            }
        else:
            for p in production:
                if p["id"] == args:
                    prod = p.copy()
                    break
            if prod is None:
                self.call("admin.redirect", "crafting/recipes/view/%s" % recipe.uuid)
        if req.ok():
            errors = {}
            # item_type
            item_type = req.param("v_item_type")
            if not item_type:
                errors["v_item_type"] = self._("This field is mandatory")
            elif item_type not in valid_item_types:
                errors["v_item_type"] = self._("Make a valid selection")
            else:
                prod["item_type"] = item_type
            # order
            prod["order"] = floatz(req.param("order"))
            # quantity
            char = self.character(req.user())
            prod["quantity"] = self.call("script.admin-expression", "quantity", errors, globs={"char": char})
            # mods
            mods = {}
            for param in params:
                val = req.param("p_%s" % param["code"]).strip()
                if val == "":
                    continue
                mods[param["code"]] = self.call("script.admin-expression", "p_%s" % param["code"], errors, globs={"char": char})
            prod["mods"] = mods
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # save
            production = [p for p in production if p["id"] != prod["id"]]
            production.append(prod)
            production.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            recipe.set("production", production)
            recipe.touch()
            recipe.store()
            self.call("admin.redirect", "crafting/recipes/view/%s" % recipe.uuid)
        fields = [
            {"name": "item_type", "label": self._("Item type"), "type": "combo", "values": item_type_values, "value": prod.get("item_type")},
            {"name": "order", "label": self._("Sorting order"), "value": prod.get("order"), "inline": True},
            {"name": "quantity", "label": self._("Quantity of items to give") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", prod.get("quantity", 1))},
        ]
        if params:
            fields.append({"type": "header", "html": self._("Override parameters")})
            fields.append({"type": "html", "html": self._("If you remain a field empty its value will be taken from the item type parameters")})
            mods = prod.get("mods", {})
            print mods
            grp = None
            for param in params:
                if param["grp"] != grp and param["grp"] != "":
                    fields.append({"type": "header", "html": param["grp"]})
                    grp = param["grp"]
                val = mods.get(param["code"])
                if val is not None:
                    val = self.call("script.unparse-expression", val)
                fields.append({"name": "p_%s" % param["code"], "label": u"%s%s" % (param["name"], self.call("script.help-icon-expressions")), "value": val})
        self.call("admin.form", fields=fields)
