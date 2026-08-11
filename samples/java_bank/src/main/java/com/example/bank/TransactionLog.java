package com.example.bank;

import java.util.ArrayList;
import java.util.List;

/**
 * In-memory transaction history. Exercises generics (List&lt;Entry&gt;), a nested
 * static class the inventory won't see (parser must), and a labeled break.
 */
public class TransactionLog {

    private final List<Entry> entries = new ArrayList<>();

    public void record(String from, String to, Money amount) {
        entries.add(new Entry(from, to, amount));
    }

    public Money totalFor(String account) {
        Money total = new Money(0, "USD");
        for (Entry entry : entries) {
            if (entry.from.equals(account) || entry.to.equals(account)) {
                total = total.plus(entry.amount);
            }
        }
        return total;
    }

    public boolean linked(String a, String b) {
        boolean found = false;
        search:
        for (Entry outer : entries) {
            if (outer.from.equals(a)) {
                for (Entry inner : entries) {
                    if (inner.to.equals(b)) {
                        found = true;
                        break search;
                    }
                }
            }
        }
        return found;
    }

    /** Nested type: invisible to the inventory, discovered by the parser. */
    static final class Entry {
        final String from;
        final String to;
        final Money amount;

        Entry(String from, String to, Money amount) {
            this.from = from;
            this.to = to;
            this.amount = amount;
        }
    }
}
