package com.example.model;

import java.io.Serializable;

public class Circle implements Shape, Serializable {

    private final double radius;
    private final Color color;

    public Circle(double radius, Color color) {
        this.radius = radius;
        this.color = color;
    }

    @Override
    public double area() {
        return Math.PI * radius * radius;
    }
}