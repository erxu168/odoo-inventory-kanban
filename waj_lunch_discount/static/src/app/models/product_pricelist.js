import { patch } from "@web/core/utils/patch";
import { ProductPricelist } from "@point_of_sale/app/models/product_pricelist";

const { DateTime } = luxon;

// Indexed by luxon's ``weekday`` (1 = Monday ... 7 = Sunday).
const WEEKDAY_FIELDS = [
    null,
    "waj_weekday_mon",
    "waj_weekday_tue",
    "waj_weekday_wed",
    "waj_weekday_thu",
    "waj_weekday_fri",
    "waj_weekday_sat",
    "waj_weekday_sun",
];

/**
 * Mirror of ``product.pricelist.item._waj_is_active_at`` on the Python side.
 *
 * @param {Object} rule product.pricelist.item record
 * @param {DateTime} [now] moment to evaluate, defaults to the current time
 * @returns {boolean} whether the rule's weekday / hour window contains ``now``
 */
export function isRuleActiveAt(rule, now = DateTime.now()) {
    if (!rule.waj_time_restricted) {
        return true;
    }
    let local = now;
    if (rule.waj_tz) {
        const zoned = now.setZone(rule.waj_tz);
        if (zoned.isValid) {
            local = zoned;
        }
    }
    if (!rule[WEEKDAY_FIELDS[local.weekday]]) {
        return false;
    }
    const hour = local.hour + local.minute / 60 + local.second / 3600;
    return hour >= (rule.waj_hour_from || 0) && hour < (rule.waj_hour_to || 0);
}

patch(ProductPricelist.prototype, {
    /**
     * Ignore rules outside their day / hour window. When a time-limited rule
     * is active it wins over the everyday rules of the same level, exactly
     * like ``product.pricelist._get_applicable_rules`` does on the server.
     */
    findBestRule(rules, quantity) {
        const now = DateTime.now();
        const active = rules.filter((rule) => isRuleActiveAt(rule, now));
        const restricted = active.filter((rule) => rule.waj_time_restricted);
        return super.findBestRule(restricted.length ? restricted : active, quantity);
    },
});
