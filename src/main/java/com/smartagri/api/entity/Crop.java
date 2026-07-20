package com.smartagri.api.entity;

import javax.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 作物实体类
 */
@Data
@Entity
@Table(name = "crop")
public class Crop {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /**
     * 作物名称
     */
    private String name;
    
    /**
     * 作物类别（1-粮食作物，2-经济作物，3-蔬菜，4-水果，5-其他）
     */
    private Integer category;
    
    /**
     * 生长周期（天）
     */
    private Integer growthCycle;
    
    /**
     * 适宜温度下限（℃）
     */
    private Double minTemperature;
    
    /**
     * 适宜温度上限（℃）
     */
    private Double maxTemperature;
    
    /**
     * 适宜湿度下限（%）
     */
    private Double minHumidity;
    
    /**
     * 适宜湿度上限（%）
     */
    private Double maxHumidity;
    
    /**
     * 作物描述
     */
    private String description;
    
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    
    /**
     * 更新时间
     */
    private LocalDateTime updateTime;
    
    /**
     * 是否删除（0-未删除，1-已删除）
     */
    private Integer isDeleted;
} 