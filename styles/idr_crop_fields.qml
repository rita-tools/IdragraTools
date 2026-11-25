<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis simplifyDrawingTol="1" version="3.10.11-A Coruña" styleCategories="AllStyleCategories" hasScaleBasedVisibilityFlag="0" readOnly="0" simplifyLocal="1" simplifyDrawingHints="1" minScale="1e+08" simplifyAlgorithm="0" labelsEnabled="0" simplifyMaxScale="1" maxScale="0">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
  </flags>
  <renderer-v2 symbollevels="0" enableorderby="0" type="singleSymbol" forceraster="0">
    <symbols>
      <symbol alpha="1" force_rhr="0" clip_to_extent="1" type="fill" name="0">
        <layer locked="0" class="SimpleFill" enabled="1" pass="0">
          <prop k="border_width_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="color" v="148,209,128,255"/>
          <prop k="joinstyle" v="bevel"/>
          <prop k="offset" v="0,0"/>
          <prop k="offset_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="offset_unit" v="MM"/>
          <prop k="outline_color" v="143,181,131,255"/>
          <prop k="outline_style" v="no"/>
          <prop k="outline_width" v="0.26"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="style" v="solid"/>
          <data_defined_properties>
            <Option type="Map">
              <Option type="QString" name="name" value=""/>
              <Option name="properties"/>
              <Option type="QString" name="type" value="collection"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </symbols>
    <rotation/>
    <sizescale/>
  </renderer-v2>
  <customproperties>
    <property key="dualview/previewExpressions">
      <value>"name"</value>
    </property>
    <property key="embeddedWidgets/count" value="0"/>
    <property key="variableNames"/>
    <property key="variableValues"/>
  </customproperties>
  <blendMode>0</blendMode>
  <featureBlendMode>0</featureBlendMode>
  <layerOpacity>1</layerOpacity>
  <SingleCategoryDiagramRenderer diagramType="Histogram" attributeLegend="1">
    <DiagramCategory minScaleDenominator="0" minimumSize="0" barWidth="5" backgroundColor="#ffffff" penWidth="0" penAlpha="255" lineSizeScale="3x:0,0,0,0,0,0" sizeType="MM" scaleBasedVisibility="0" height="15" opacity="1" maxScaleDenominator="1e+08" sizeScale="3x:0,0,0,0,0,0" backgroundAlpha="255" rotationOffset="270" lineSizeType="MM" width="15" scaleDependency="Area" labelPlacementMethod="XHeight" diagramOrientation="Up" penColor="#000000" enabled="0">
      <fontProperties description="MS Shell Dlg 2,8,-1,5,50,0,0,0,0,0" style=""/>
    </DiagramCategory>
  </SingleCategoryDiagramRenderer>
  <DiagramLayerSettings showAll="1" obstacle="0" dist="0" placement="1" linePlacementFlags="18" zIndex="0" priority="0">
    <properties>
      <Option type="Map">
        <Option type="QString" name="name" value=""/>
        <Option name="properties"/>
        <Option type="QString" name="type" value="collection"/>
      </Option>
    </properties>
  </DiagramLayerSettings>
  <geometryOptions removeDuplicateNodes="0" geometryPrecision="0">
    <activeChecks/>
    <checkConfiguration type="Map">
      <Option type="Map" name="QgsGeometryGapCheck">
        <Option type="double" name="allowedGapsBuffer" value="0"/>
        <Option type="bool" name="allowedGapsEnabled" value="false"/>
        <Option type="QString" name="allowedGapsLayer" value=""/>
      </Option>
    </checkConfiguration>
  </geometryOptions>
  <fieldConfiguration>
    <field name="fid">
      <editWidget type="Hidden">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="name">
      <editWidget type="TextEdit">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="id_soil">
      <editWidget type="Range">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="id_soiluse">
      <editWidget type="Range">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="id_irr">
      <editWidget type="Range">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="id_wsource">
      <editWidget type="Range">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="id_wstation">
      <editWidget type="Range">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
    <field name="id_gw_well">
      <editWidget type="Range">
        <config>
          <Option/>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <aliases>
    <alias name="" index="0" field="fid"/>
    <alias name="" index="1" field="name"/>
    <alias name="" index="2" field="id_soil"/>
    <alias name="" index="3" field="id_soiluse"/>
    <alias name="" index="4" field="id_irr"/>
    <alias name="" index="5" field="id_wsource"/>
    <alias name="" index="6" field="id_wstation"/>
    <alias name="" index="7" field="id_gw_well"/>
  </aliases>
  <excludeAttributesWMS/>
  <excludeAttributesWFS/>
  <defaults>
    <default applyOnUpdate="0" expression="" field="fid"/>
    <default applyOnUpdate="0" expression="" field="name"/>
    <default applyOnUpdate="0" expression="" field="id_soil"/>
    <default applyOnUpdate="0" expression="" field="id_soiluse"/>
    <default applyOnUpdate="0" expression="" field="id_irr"/>
    <default applyOnUpdate="0" expression="" field="id_wsource"/>
    <default applyOnUpdate="0" expression="" field="id_wstation"/>
    <default applyOnUpdate="0" expression="" field="id_gw_well"/>
  </defaults>
  <constraints>
    <constraint exp_strength="0" constraints="3" field="fid" unique_strength="1" notnull_strength="1"/>
    <constraint exp_strength="0" constraints="0" field="name" unique_strength="0" notnull_strength="0"/>
    <constraint exp_strength="0" constraints="0" field="id_soil" unique_strength="0" notnull_strength="0"/>
    <constraint exp_strength="0" constraints="0" field="id_soiluse" unique_strength="0" notnull_strength="0"/>
    <constraint exp_strength="0" constraints="0" field="id_irr" unique_strength="0" notnull_strength="0"/>
    <constraint exp_strength="0" constraints="0" field="id_wsource" unique_strength="0" notnull_strength="0"/>
    <constraint exp_strength="0" constraints="0" field="id_wstation" unique_strength="0" notnull_strength="0"/>
    <constraint exp_strength="0" constraints="0" field="id_gw_well" unique_strength="0" notnull_strength="0"/>
  </constraints>
  <constraintExpressions>
    <constraint exp="" desc="" field="fid"/>
    <constraint exp="" desc="" field="name"/>
    <constraint exp="" desc="" field="id_soil"/>
    <constraint exp="" desc="" field="id_soiluse"/>
    <constraint exp="" desc="" field="id_irr"/>
    <constraint exp="" desc="" field="id_wsource"/>
    <constraint exp="" desc="" field="id_wstation"/>
    <constraint exp="" desc="" field="id_gw_well"/>
  </constraintExpressions>
  <expressionfields/>
  <attributeactions>
    <defaultAction key="Canvas" value="{00000000-0000-0000-0000-000000000000}"/>
  </attributeactions>
  <attributetableconfig actionWidgetStyle="dropDown" sortOrder="0" sortExpression="">
    <columns>
      <column width="-1" hidden="1" type="field" name="fid"/>
      <column width="-1" hidden="0" type="field" name="name"/>
      <column width="-1" hidden="0" type="field" name="id_soil"/>
      <column width="-1" hidden="0" type="field" name="id_soiluse"/>
      <column width="-1" hidden="0" type="field" name="id_irr"/>
      <column width="-1" hidden="0" type="field" name="id_wsource"/>
      <column width="-1" hidden="0" type="field" name="id_wstation"/>
      <column width="-1" hidden="0" type="field" name="id_gw_well"/>
      <column width="-1" hidden="1" type="actions"/>
    </columns>
  </attributetableconfig>
  <conditionalstyles>
    <rowstyles/>
    <fieldstyles/>
  </conditionalstyles>
  <storedexpressions/>
  <editform tolerant="1">C:/Users/enrico/AppData/Roaming/QGIS/QGIS3\profiles\default/python/plugins\idragra4qgis/layerforms/crop_field_dialog.ui</editform>
  <editforminit>formOpen</editforminit>
  <editforminitcodesource>1</editforminitcodesource>
  <editforminitfilepath>C:/Users/enrico/AppData/Roaming/QGIS/QGIS3\profiles\default/python/plugins\idragra4qgis/layerforms/crop_field_dialog.py</editforminitfilepath>
  <editforminitcode><![CDATA[# -*- coding: utf-8 -*-
"""
QGIS forms can have a Python function that is called when the form is
opened.

Use this function to add extra logic to your forms.

Enter the name of the function in the "Python Init function"
field.
An example follows:
"""
from qgis.PyQt.QtWidgets import QWidget

def my_form_open(dialog, layer, feature):
	geom = feature.geometry()
	control = dialog.findChild(QWidget, "MyLineEdit")
]]></editforminitcode>
  <featformsuppress>0</featformsuppress>
  <editorlayout>uifilelayout</editorlayout>
  <editable/>
  <labelOnTop/>
  <widgets/>
  <previewExpression>"name"</previewExpression>
  <mapTip></mapTip>
  <layerGeometryType>2</layerGeometryType>
</qgis>
