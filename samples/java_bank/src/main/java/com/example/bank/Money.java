package com.example.bank;

/** Immutable money value. Plain final class (version-agnostic; no build file needed). */
public final class Money {

    private final long cents;
    private final String currency;

    public Money(long cents, String currency) {
        if (cents < 0) {
            throw new IllegalArgumentException("cents must be >= 0");
        }
        this.cents = cents;
        this.currency = currency;
    }

    public long cents() {
        return cents;
    }

    public String currency() {
        return currency;
    }

    public Money plus(Money other) {
        return new Money(cents + other.cents, currency);
    }

    public double toDouble() {
        return cents / 100.0;
    }
}
