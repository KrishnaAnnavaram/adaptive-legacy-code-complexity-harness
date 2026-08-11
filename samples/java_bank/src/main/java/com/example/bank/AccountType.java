package com.example.bank;

/** Account tiers. Exercises enum constants with constructor args + a loop. */
public enum AccountType {

    BASIC(0),
    SILVER(1000),
    GOLD(10000);

    private final double threshold;

    AccountType(double threshold) {
        this.threshold = threshold;
    }

    public double threshold() {
        return threshold;
    }

    public static AccountType forBalance(double balance) {
        AccountType best = BASIC;
        for (AccountType type : values()) {
            if (balance >= type.threshold) {
                best = type;
            }
        }
        return best;
    }
}
