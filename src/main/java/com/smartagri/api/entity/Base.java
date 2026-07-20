package com.smartagri.api.entity;

import javax.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 农业基地实体类
 */
@Data
@Entity
@Table(name = "land_base")
public class Base {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /**
     * 基地名称
     */
    private String name;
    
    /**
     * 基地地址
     */
    private String address;
    
    /**
     * 基地总面积（亩）
     */
    private Double area;
    
    /**
     * 基地经度
     */
    private Double longitude;
    
    /**
     * 基地纬度
     */
    private Double latitude;
    
    /**
     * 基地描述
     */
    private String description;
    
    /**
     * 负责人ID
     */
    private Long managerId;
    
    /**
     * 联系电话
     */
    private String contactPhone;
    
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