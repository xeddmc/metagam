/*
 * Objects Manager
 */
var ObjectsManager = Ext.extend(Object, {
    constructor: function () {
        var self = this;
        self.timerInterval = 10;
        self.clear();
    },

    /*
     * Remove all objects and reinitialize
     */
    clear: function () {
        var self = this;
        self.markNeedUpdate();
        self.objects = [];
    },

    /*
     * Get current time in milliseconds
     */
    getTime: function () {
        return (new Date()).getTime();
    },

    /*
     * Register new object
     */
    addObject: function (obj) {
        var self = this;
        self.markNeedUpdate();
        self.objects.push(obj);
    },

    /*
     * Destroy object by id
     */
    destroyObject: function (objId) {
        var self = this;
        self.markNeedUpdate();
        for (var i = 0; i < self.objects.length; i++) {
            var obj = self.objects[i];
            if (obj.id == objId) {
                self.objects.splice(i, 1);
                obj.destroy();
                break;
            }
        }
    },

    /*
     * Run timer to update objects
     */
    run: function () {
        var self = this;
        if (self.running) {
            return;
        }
        self.running = true;
        self.timerTick();
    },

    /*
     * Process timer event
     */
    timerTick: function () {
        var self = this;
        try {
            var now = self.getTime();
            self.update(now);
        } catch (e) {
            try { Game.error(gt.gettext('Exception'), e); } catch (e2) {}
        }
        setTimeout(function () {
            self.timerTick();
        }, self.timerInterval);
    },

    /*
     * Update all objects
     */
    update: function (now) {
        var self = this;
        if (!self.needUpdate) {
            return;
        }
        self.needUpdate = false;
        for (var i = 0; i < self.objects.length; i++) {
            var obj = self.objects[i];
            obj.update(now);
            if (obj.needUpdate) {
                self.needUpdate = true;
            }
        }
    },

    /*
     * If something changed in the object manager, and it needs update
     */
    markNeedUpdate: function () {
        var self = this;
        self.needUpdate = true;
    }
});

/*
 * Generic Object
 */
var GenericObject = Ext.extend(Object, {
    constructor: function (manager, id) {
        var self = this;
        self.manager = manager;
        self.id = id;
        self.params = [];
        self.needUpdate = true;
    },

    /*
     * Register new parameter for the object
     */
    addParam: function (param) {
        var self = this;
        self.params.push(param);
    },

    /*
     * Update object
     */
    update: function (now) {
        var self = this;
        if (!self.needUpdate) {
            return;
        }
        self.needUpdate = false;
        for (var i = 0; i < self.params.length; i++) {
            var param = self.params[i];
            param.update(now);
            if (param.needUpdate) {
                self.needUpdate = true;
            }
        }
    },

    /*
     * Destroy object
     */
    destroy: function () {
        var self = this;
        self.markNeedUpdate();
    },

    /*
     * If something changed in the object, and it needs update
     */
    markNeedUpdate: function () {
        var self = this;
        self.needUpdate = true;
        self.manager.markNeedUpdate();
    }
});

/*
 * Generic Object Parameter
 */
var GenericObjectParam = Ext.extend(Object, {
    constructor: function (obj, id, value) {
        var self = this;
        self.obj = obj;
        self.id = id;
        self.value = value;
        self.needUpdate = true;
    },

    /*
    * Update object parameter
    */
    update: function (now) {
        var self = this;
        if (!self.needUpdate) {
            return;
        }
        self.needUpdate = false;
        var val;
        if (self.value instanceof DynamicValue) {
            val = self.value.evaluateAndForget(now);
            if (self.value.dynamic) {
                self.needUpdate = true;
            }
        } else {
            val = self.value;
        }
        self.applyValue(val);
    },

    /*
    * Apply parameter value
    */
    applyValue: function (val) {
    }
});

wait(['mmoscript'], function () {
    loaded('objects');
});