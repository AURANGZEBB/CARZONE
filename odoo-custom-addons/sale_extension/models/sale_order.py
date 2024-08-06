# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def default_get(self, field_list):
        result = super(SaleOrder, self).default_get(field_list)
        project = self.env["project.project"].search([])
        if project:
            result["project_id"] = project[0].id
        return result

    title = fields.Selection([('mr', 'Mr.'), ('mrs', 'Mrs.'), ('miss', 'Miss')])
    is_insurance = fields.Boolean(string="Is Insurance Claim")
    insurance_company_id = fields.Many2one('res.partner', string='Insurance Company', auto_join=True, tracking=True,
                                           domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    project_id = fields.Many2one('project.project', required=True)
    policy_no = fields.Char("Policy No.")
    lpo_no = fields.Char("LPO No")
    lpo_date = fields.Date("LPO Date")
    claim_no = fields.Char("Claim No.")
    vehicle = fields.Many2one("fleet.vehicle", string="Vehicle", store=True,
                              domain="[('cc_partner', '=', partner_id)]")
    registration_no = fields.Char(string="Registration Number", related="vehicle.license_plate")
    vehicle_make = fields.Many2one("fleet.vehicle.model.brand", related="vehicle.cc_vehicle_make",
                                   string="Vehicle Make")
    vehicle_model = fields.Many2one("fleet.vehicle.model", related="vehicle.model_id", string="Vehicle Model")
    vehicle_type = fields.Many2one("vehicle.type.custom", string="Vehicle Type",
                                   related="vehicle.cc_vehicle_type")
    vehicle_color = fields.Many2one("vehicle.color", related="vehicle.cc_vehicle_color", string="Vehicle Color")
    vin = fields.Char(string="VIN", related="vehicle.vin_sn")
    engin_no = fields.Char(string="Engin No.", related="vehicle.cc_engin_no")
    gears = fields.Selection([('automatic', 'Automatic'),
                              ('manual', 'Manual')], string='Gears', related="vehicle.cc_gears")
    year = fields.Char(string="Year", related="vehicle.cc_year")
    fuel_type = fields.Selection([
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('gas', 'Gasoline'),
        ('electric', 'Electrical')
    ], string="Fuel Type", related="vehicle.cc_fuel_type")
    num_word = fields.Char(string="Amount In Words:", compute='_compute_amount_in_word')
    is_job_card_created = fields.Boolean(string="Is Job Created?")

    def _compute_amount_in_word(self):
        for rec in self:
            rec.num_word = str(rec.currency_id.amount_to_text(rec.amount_total)) + ' only'

    def create_material_requisition(self, job_card_id):
        """
        Create material requisition
        """
        material_requisition_obj = self.env['material.purchase.requisition']
        employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)])
        material_requisition_id = material_requisition_obj.create({
            'employee_id': employee_id.id,
            'department_id': employee_id.department_id.id,
            'request_date': fields.Date.today(),
            'task_id': job_card_id.id
        })
        return material_requisition_id

    def create_job_card(self):
        """
        Create Job card
        """
        if self.state not in ['sale']:
            raise ValidationError(_('Confirm the order first.'))

        job_card_obj = self.env['project.task']
        job_cost_sheet = self.env['job.cost.sheet']
        material_requisition_line = self.env['material.purchase.requisition.line']

        job_card = job_card_obj.create({
            'partner_id': self.partner_id.id,
            'is_jobcard': True,
            'title': self.title,
            'is_insurance': self.is_insurance,
            'insurance_company': self.insurance_company_id.id,
            'project_id': self.project_id.id,
            'policy_no': self.policy_no,
            'lpo_no': self.lpo_no,
            'lpo_date': self.lpo_date,
            'claim_no': self.claim_no,
            'cc_vehicle': self.vehicle.id,
            'sale_order_id': self.id,
        })
        if job_card and job_card.id:
            self.is_job_card_created = True

        if self.order_line:
            cost_sheet_lines = self.order_line.filtered(lambda x: x.cost_type not in ['material', 'spare_parts'])
            requisition_lines = self.order_line.filtered(lambda x: x.cost_type in ['material', 'spare_parts'])
            if cost_sheet_lines:
                for line in cost_sheet_lines:
                    job_cost_sheet.create({
                        'cost_type': line.cost_type,
                        'product_id': line.product_id.id,
                        'account_id': line.product_id.categ_id.property_account_income_categ_id.id,
                        'account_analytic_id': None,
                        'quantity': line.product_uom_qty,
                        'uom_id': line.product_uom.id,
                        'cc_sale_price': line.cc_sale_price,
                        'price_unit': line.price_unit,
                        'invoice_line_tax_ids': line.tax_id,
                        'price_subtotal': line.price_subtotal,
                        'task_id': job_card.id,
                        'name': line.name,
                        'discount': line.discount,
                        'cc_check_box': True
                    })

            if requisition_lines:
                material_requisition_id = self.create_material_requisition(job_card)
                for line in requisition_lines:
                    material_requisition_line.create({
                        'requisition_type': 'internal',
                        'barcode': line.product_id.barcode,
                        'product_id': line.product_id.id,
                        'description': line.product_id.name,
                        'qty': line.product_uom_qty,
                        'uom': line.product_uom.id,
                        'requisition_id': material_requisition_id.id,
                    })

        return True


    def separate_order_lines(self):
        """
        Separate cost sheet lines
        """
        line = []

        for rec in self:
            if rec.order_line:
                other_lines = self.order_line.filtered(lambda x: x.cost_type not in ['material', 'spare_parts', 'labour'])
                labour_lines = self.order_line.filtered(lambda x: x.cost_type in ['labour'])
                material_lines = self.order_line.filtered(lambda x: x.cost_type in ['material', 'spare_parts'])
                if material_lines:
                    for type in sorted(set(material_lines.mapped('cost_type')), reverse=True):
                        cost_sheet_list = []
                        cost_sheet_list.append(rec.order_line.filtered(lambda x: x.cost_type == type))
                        line.append(cost_sheet_list)
                if labour_lines:
                    for type in sorted(set(labour_lines.mapped('cost_type')), reverse=True):
                        cost_sheet_list = []
                        cost_sheet_list.append(rec.order_line.filtered(lambda x: x.cost_type == type))
                        line.append(cost_sheet_list)
                if other_lines:
                    for type in sorted(set(other_lines.mapped('cost_type')), reverse=True):
                        cost_sheet_list = []
                        cost_sheet_list.append(rec.order_line.filtered(lambda x: x.cost_type == type))
                        line.append(cost_sheet_list)
        return line


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cost_type = fields.Selection(
        [('spare_parts', 'Spare Parts'),
         ('material', 'Material'),
         ('overhead', 'Overhead'),
         ('labour', 'Labour'),
         ('consumables', 'Consumables'),
         ('paint_material', 'Paint Material'),
         ('paint_material_cog', 'Paint Material COG'),
         ('mechanical_cog', 'Mechanical COG'),
         ('sublet', 'Sublet'),
         ('tyre', 'Tyre'),
         ('scrap', 'Scrap'),

         ],
        string='Department',
        default='spare_parts',
    )

    cc_sale_price = fields.Float(string="Cost Price", related="product_id.standard_price")

    def action_increase_price(self):
        """
        Increase price by 10 %
        """
        for rec in self:
            if rec.price_unit:
                rec.price_unit = rec.price_unit * 1.1


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sale_order_id = fields.Many2one("sale.order", string="Sale Order")
    account_move_id = fields.Many2one("account.move", string="Bills")

