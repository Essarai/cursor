package com.smartagri.api.entity;

import javax.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 地块实体类
 */
@Data
@Entity
@Table(name = "land_block")
public class LandBlock {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /**
     * 所属基地ID
     */
    private Long baseId;
    
    /**
     * 地块名称
     */
    private String name;
    
    /**
     * 地块编号
     */
    private String code;
    
    /**
     * 地块面积（亩）
     */
    private Double area;
    
    /**
     * 地块类型（1-大田，2-大棚，3-温室，4-其他）
     */
    private Integer type;
    
    /**
     * 土壤类型
     */
    private String soilType;
    
    /**
     * 经度
     */
    private Double longitude;
    
    /**
     * 纬度
     */
    private Double latitude;
    
    /**
     * 地块描述
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