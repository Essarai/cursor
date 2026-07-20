package com.smartagri.api.entity;

import javax.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 种植记录实体类
 */
@Data
@Entity
@Table(name = "planting")
public class Planting {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /**
     * 地块ID
     */
    private Long landBlockId;
    
    /**
     * 作物ID
     */
    private Long cropId;
    
    /**
     * 种植面积（亩）
     */
    private Double area;
    
    /**
     * 种植数量
     */
    private Integer quantity;
    
    /**
     * 种植时间
     */
    private LocalDateTime plantTime;
    
    /**
     * 预计收获时间
     */
    private LocalDateTime estimatedHarvestTime;
    
    /**
     * 实际收获时间
     */
    private LocalDateTime actualHarvestTime;
    
    /**
     * 预计产量（kg）
     */
    private Double estimatedYield;
    
    /**
     * 实际产量（kg）
     */
    private Double actualYield;
    
    /**
     * 种植状态（1-已种植，2-生长中，3-已收获，4-已废弃）
     */
    private Integer status;
    
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