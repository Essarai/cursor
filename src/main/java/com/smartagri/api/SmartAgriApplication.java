package com.smartagri.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

/**
 * 智慧农业应用主类
 */
@SpringBootApplication
@EnableJpaAuditing
public class SmartAgriApplication {

    public static void main(String[] args) {
        SpringApplication.run(SmartAgriApplication.class, args);
    }
} 