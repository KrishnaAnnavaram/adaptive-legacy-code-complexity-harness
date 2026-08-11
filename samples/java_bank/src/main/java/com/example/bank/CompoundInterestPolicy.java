package com.example.bank;

/** Compounding interest. Exercises implements + recursion + a do/while loop. */
public class CompoundInterestPolicy implements InterestPolicy {

    private final double base;

    public CompoundInterestPolicy(double base) {
        this.base = base;
    }

    @Override
    public double rate(int month) {
        if (month <= 1) {
            return base;
        }
        return base + 0.001 * rate(month - 1);
    }

    public int monthsToReach(double target) {
        double factor = 1.0;
        int months = 0;
        do {
            factor += factor * base;
            months++;
        } while (factor < target && months < 1000);
        return months;
    }
}
