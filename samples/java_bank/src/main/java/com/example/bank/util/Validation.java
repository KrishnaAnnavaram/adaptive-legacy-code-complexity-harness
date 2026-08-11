package com.example.bank.util;

/** Stateless input checks. Second package + static methods (cross-package calls). */
public final class Validation {

    private Validation() {
    }

    public static void requirePositive(double amount) {
        if (amount <= 0 || Double.isNaN(amount)) {
            throw new IllegalArgumentException("amount must be positive");
        }
    }

    public static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
