from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
import io
import base64
from odoo.tools.misc import xlsxwriter
from odoo.exceptions import ValidationError, UserError


class InvoiceWizard(models.TransientModel):
    _name = 'invoice.wizard'
    _description = 'Invoice Wizard'

    @api.model
    def default_get(self, field_list):
        res = super(InvoiceWizard, self).default_get(field_list)
        res.update({
            'year': date.today().strftime("%Y"),
        })
        return res

    report_selection = fields.Selection(
        [('today', 'Today'), ('yesterday', 'Yesterday'), ('date_range', 'Date Range'),
         ('job_card', 'Job Card'), ('sales_person', 'Sales Person')],
        string="Report Type", required=True, default='date')
    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='End Date')
    month = fields.Selection([('jan', 'January'), ('feb', 'February'), ('march', 'March'), ('april', 'April'),
                              ('may', 'May'), ('june', 'June'), ('july', 'July'), ('aug', 'August'),
                              ('sept', 'September'), ('oct', 'October'), ('nov', 'November'), ('dec', 'December')],
                             string="Month")
    year = fields.Char(string="Year")
    job_card = fields.Many2one("project.task", string="Job Card")
    spare_parts_total = fields.Boolean(string="Spare Parts Total")
    consumables_total = fields.Boolean(string="Consumables total")
    labour_total = fields.Boolean(string="Labour total")
    body_shop = fields.Boolean(string="Body Shop")
    mechanical = fields.Boolean(string="Mechanical")
    sublet = fields.Boolean(string="Sublet")
    sales_person_ids = fields.Many2many(
        'res.users', string='Sales Persons'
    )

    def _get_invoice(self, selection):
        domain = []
        if selection == "today":
            domain = [('invoice_date', '=', datetime.today().date()),
                      ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
                       ('state', 'not in', ['cancel'])]

        elif selection == "yesterday":
            domain = [('invoice_date', '=', (datetime.today() - timedelta(1)).date()),
                      ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
                       ('state', 'not in', ['cancel'])]

        elif selection == "date_range" and self.date_from and self.date_to:
            domain = [('invoice_date', '>=', self.date_from), ('invoice_date', '<=', self.date_to),
                      ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
                       ('state', 'not in', ['cancel'])]

        elif selection == "job_card" and self.job_card:
            domain = [('cc_job_card', '=', self.job_card.id),
                      ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
                       ('state', 'not in', ['cancel'])]

        elif selection == "sales_person" and self.sales_person_ids:
            domain = [('invoice_user_id', '=', self.sales_person_ids.ids),
                      ('move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')),
                       ('state', 'not in', ['cancel'])]

        return self.env['account.move'].search(domain)

    def _get_todays_invoice_data(self):
        invoice_lines = []
        invoice = []
        account_invoices = self._get_invoice("today")
        if account_invoices:
            for invoice in account_invoices:
                account_invoice_lines = self.env['account.move'].search([('move_id', '=', invoice.id)])
                if account_invoice_lines:
                    invoice_lines.append(account_invoice_lines)
        return invoice_lines

    def _get_spare_parts(self, selection):
        account_invoices = self._get_invoice(selection)
        invoice_line_ids = account_invoices.mapped("invoice_line_ids")
        spare_parts_lines = []
        total = 0
        if account_invoices and invoice_line_ids:
            for line in invoice_line_ids.filtered(lambda x: x.cc_cost_type == "spare_parts"):
                total += line.price_subtotal
                spare_parts_lines.append(line)
        return account_invoices, total

    def _get_labour(self, selection):
        account_invoices = self._get_invoice(selection)
        invoice_line_ids = account_invoices.mapped("invoice_line_ids")
        labour_lines = []
        total = 0
        if account_invoices and invoice_line_ids:
            for line in invoice_line_ids.filtered(lambda x: x.cc_cost_type == "labour"):
                total += line.price_subtotal
                labour_lines.append(line)
        return account_invoices, total

    def _get_body_shop(self, selection):
        account_invoices = self._get_invoice(selection)
        filtered_account_invoices = account_invoices.filtered(lambda x: x.repair_category == "BODYSHOP")
        invoice_line_ids = filtered_account_invoices.mapped("invoice_line_ids")
        body_shop_lines = []
        total = 0
        if account_invoices and invoice_line_ids:
            for line in invoice_line_ids:
                total += line.price_subtotal
                body_shop_lines.append(line)
        return filtered_account_invoices, total

    def _get_job_card_invoice(self, selection, job_card):
        account_invoices = self._get_invoice(selection, job_card=job_card)
        invoice_line_ids = account_invoices.mapped("invoice_line_ids")
        body_shop_lines = []
        total = 0
        if account_invoices and invoice_line_ids:
            for line in invoice_line_ids:
                total += line.price_subtotal
                body_shop_lines.append(line)
        return account_invoices, total

    def _get_consumables(self, selection):
        account_invoices = self._get_invoice(selection)
        invoice_line_ids = account_invoices.mapped("invoice_line_ids")
        consumables_lines = []
        total = 0
        if account_invoices and invoice_line_ids:
            for line in invoice_line_ids.filtered(lambda x: x.cc_cost_type == "consumables"):
                total += line.price_subtotal
                consumables_lines.append(line)
        return account_invoices, total

    def _get_sublet(self, selection):
        account_invoices = self._get_invoice(selection)
        invoice_line_ids = account_invoices.mapped("invoice_line_ids")
        sublet_lines = []
        total = 0
        if account_invoices and invoice_line_ids:
            for line in invoice_line_ids.filtered(lambda x: x.cc_cost_type == "sublet"):
                total += line.price_subtotal
                sublet_lines.append(line)
        return account_invoices, total

    def _get_mechanical(self, selection):
        account_invoices = self._get_invoice(selection)
        invoice_line_ids = account_invoices.mapped("invoice_line_ids")
        sublet_lines = []
        total = 0
        if account_invoices and invoice_line_ids:
            for line in invoice_line_ids.filtered(lambda x: x.cc_cost_type == "mechanical_cog"):
                total += line.price_subtotal
                sublet_lines.append(line)
        return account_invoices, total

    def _get_sale_person_invoice_data(self, selection, sale_person_id):
        account_invoices = self._get_invoice(selection, sales_person_ids=sale_person_id)
        invoice_line_ids = account_invoices.mapped("invoice_line_ids")
        lines = []
        total = 0
        if account_invoices and invoice_line_ids:
            for line in invoice_line_ids:
                total += line.price_subtotal
                lines.append(line)
        return account_invoices, total

    def write_invoice_data(self, sheet, format_header, content, row, price, invoices, filter, total, lang_id):
        row = row
        i = 1
        for invoice in invoices:
            if invoice.mapped("invoice_line_ids").filtered(lambda x: x.cc_cost_type == filter):
                date = False
                if invoice.invoice_date:
                    date = fields.Date.from_string(str(invoice.invoice_date)).strftime(lang_id.date_format)
                sheet.write(row, 0, i, content)
                sheet.write(row, 1, invoice.name, content)
                sheet.write(row, 2, invoice.cc_job_card.name or " ", content)
                sheet.write(row, 3, invoice.insurance_company_id.name or " ", content)
                sheet.write(row, 4, invoice.partner_id.name or " ", content)
                sheet.write(row, 5, date or " ", content)
                sheet.write(row, 6, invoice.cc_registration_no or " ", content)
                sheet.write(row, 7, " ".join(invoice.user_ids.mapped("name")) or " ", content)
                sheet.write(row, 8, invoice.invoice_user_id.name or " ", content)
                invoice_row = row

                for line in invoice.mapped("invoice_line_ids").filtered(lambda x: x.cc_cost_type == filter):
                    sheet.write(row, 9, line.barcode_custom or " ", content)
                    sheet.write(row, 10, line.product_id.name or " ", content)
                    sheet.write(row, 11, line.quantity or " ", content)
                    sheet.write(row, 12, line.cc_sale_price or " ", price)
                    sheet.write(row, 13, line.cloned_price_unit or " ", price)
                    sheet.write(row, 14, line.l10n_ae_vat_amount or " ", price)
                    sheet.write(row, 15, line.price_subtotal or 0.0, price)
                    row += 1
                #sheet.write(invoice_row, 16, total or 0.0, price)
                sheet.write(invoice_row, 16, invoice.state or " ", content)
                row += 1
                i += 1
        return row

    def write_invoice_data_without_cost_sheet(self, sheet, format_header, content, row, price, invoices, total,
                                              lang_id):
        row = row
        i = 1
        for invoice in invoices:
            if invoice.mapped("invoice_line_ids"):
                date = False
                if invoice.invoice_date:
                    date = fields.Date.from_string(str(invoice.invoice_date)).strftime(lang_id.date_format)
                sheet.write(row, 0, i, content)
                sheet.write(row, 1, invoice.name, content)
                sheet.write(row, 2, invoice.cc_job_card.name or " ", content)
                sheet.write(row, 3, invoice.insurance_company_id.name or " ", content)
                sheet.write(row, 4, invoice.partner_id.name or " ", content)
                sheet.write(row, 5, date or " ", content)
                sheet.write(row, 6, invoice.cc_registration_no or " ", content)
                sheet.write(row, 7, " ".join(invoice.user_ids.mapped("name")) or " ", content)
                sheet.write(row, 8, invoice.invoice_user_id.name or " ", content)
                invoice_row = row

                for line in invoice.mapped("invoice_line_ids"):
                    sheet.write(row, 9, line.barcode_custom or " ", content)
                    sheet.write(row, 10, line.product_id.name or " ", content)
                    sheet.write(row, 11, line.quantity or " ", content)
                    sheet.write(row, 12, line.cc_sale_price or " ", price)
                    sheet.write(row, 13, line.cloned_price_unit or " ", price)
                    sheet.write(row, 14, line.l10n_ae_vat_amount or " ", price)
                    sheet.write(row, 15, line.price_subtotal or 0.0, price)
                    row += 1
                #sheet.write(invoice_row, 16, total or 0.0, price)
                sheet.write(invoice_row, 16, invoice.state or " ", content)
                row += 1
                i += 1

        return row

    def action_print_xlsx(self):
        if not self.report_selection:
            raise UserError(_("No Options Selected!!"))

        lang = self.env.user.lang
        lang_id = self.env['res.lang'].search([('code', '=', lang)])[0]
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Invoice Report')

        # Formats
        ############################################################
        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 2, 18)
        sheet.set_column(3, 3, 30)
        sheet.set_column(4, 4, 30)
        sheet.set_column(5, 5, 13)
        sheet.set_column(6, 6, 13)
        sheet.set_column(7, 7, 13)
        sheet.set_column(8, 8, 13)
        sheet.set_column(9, 9, 13)
        sheet.set_column(10, 10, 30)
        sheet.set_column(11, 11, 5)
        sheet.set_column(12, 12, 10)
        sheet.set_column(14, 14, 10)
        sheet.set_column(17, 17, 13)

        format_title = workbook.add_format({
            'bold': True,
            'align': 'center',
            'font_size': 12,
            'font': 'Arial',
            'border': False
        })
        format_header = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'font': 'Arial',
            'align': 'left',
            # 'border': True
        })
        content = workbook.add_format({
            'bold': False,
            'font_size': 9,
            'align': 'left',
            'font': 'Arial',
            'text_wrap': True,
        })
        price = workbook.add_format({
            'bold': False,
            'font_size': 9,
            'align': 'right',
            'font': 'Arial',
            'text_wrap': True,
        })
        sheet.merge_range('A1:R1', 'Invoice Report', format_title)
        row = 1

        row += 1
        if not self.spare_parts_total and not self.labour_total and not self.consumables_total and not self.body_shop and not self.sublet and not self.mechanical :
            invoices = self._get_invoice(self.report_selection)
            total = 0.0
            if invoices:
                headers = ['Sr.No.', 'Invoice Number', 'Job Card', 'Insurance Company', 'Vehicle Owner', 'Date',
                           'Vehicle Number','Assignees', 'Sales Person', 'Part No', 'Product', 'Qty', 'Cost Price', 'Sale Price', 'Tax Amount', 'Subtotal', 'State', ]
                for col_num, header in enumerate(headers):
                    sheet.write(row, col_num, header, format_header)
                row += 1
                if invoices.mapped("invoice_line_ids"):
                    for line in invoices.mapped("invoice_line_ids"):
                        total += line.price_subtotal
                row_count = self.write_invoice_data_without_cost_sheet(sheet, format_header, content, row,
                                                                       price, invoices, total, lang_id)
                row = row_count
                row += 1

        if self.spare_parts_total:
            invoices, total = self._get_spare_parts(self.report_selection)
            if invoices and total:
                sheet.merge_range('A' + str(row) + ':J' + str(row), 'Spare Parts => Total Amount: '+ str(total), format_header)
                row += 1
                headers = ['Sr.No.', 'Invoice Number', 'Job Card', 'Insurance Company', 'Vehicle Owner', 'Date',
                           'Vehicle Number','Assignees', 'Sales Person', 'Part No', 'Product', 'Qty', 'Cost Price', 'Sale Price', 'Tax Amount', 'Subtotal', 'State', ]
                for col_num, header in enumerate(headers):
                    sheet.write(row, col_num, header, format_header)
                row += 1
                row_count = self.write_invoice_data(sheet, format_header, content, row, price, invoices,
                                                    "spare_parts", total, lang_id)
                row = row_count
                row += 1

        if self.labour_total:
            invoices, total = self._get_labour(self.report_selection)
            if invoices and total:
                row += 1
                sheet.merge_range('A' + str(row) + ':J' + str(row), 'Labour => Total Amount: '+ str(total), format_header)
                row += 1
                headers = ['Sr.No.', 'Invoice Number', 'Job Card', 'Insurance Company', 'Vehicle Owner', 'Date',
                           'Vehicle Number','Assignees', 'Sales Person', 'Part No', 'Product', 'Qty', 'Cost Price', 'Sale Price', 'Tax Amount', 'Subtotal', 'State', ]
                for col_num, header in enumerate(headers):
                    sheet.write(row, col_num, header, format_header)
                row += 1
                row_count = self.write_invoice_data(sheet, format_header, content, row, price, invoices,
                                                    "labour", total, lang_id)
                row = row_count
                row += 1

        if self.body_shop:
            invoices, total = self._get_body_shop(self.report_selection)
            if invoices and total:
                row += 1
                sheet.merge_range('A' + str(row) + ':J' + str(row), 'Body Shop => Total Amount: '+ str(total), format_header)
                row += 1
                headers = ['Sr.No.', 'Invoice Number', 'Job Card', 'Insurance Company', 'Vehicle Owner', 'Date',
                           'Vehicle Number','Assignees', 'Sales Person', 'Part No', 'Product', 'Qty', 'Cost Price', 'Sale Price', 'Tax Amount', 'Subtotal', 'State', ]
                for col_num, header in enumerate(headers):
                    sheet.write(row, col_num, header, format_header)
                row += 1
                row_count = self.write_invoice_data_without_cost_sheet(sheet, format_header, content, row,
                                                                       price, invoices, total, lang_id)
                row = row_count
                row += 1
        if self.consumables_total:
            invoices, total = self._get_consumables(self.report_selection)
            if invoices and total:
                row += 1
                sheet.merge_range('A' + str(row) + ':J' + str(row), 'Consumables => Total Amount: '+ str(total), format_header)
                row += 1
                headers = ['Sr.No.', 'Invoice Number', 'Job Card', 'Insurance Company', 'Vehicle Owner', 'Date',
                           'Vehicle Number','Assignees', 'Sales Person', 'Part No', 'Product', 'Qty', 'Cost Price', 'Sale Price', 'Tax Amount', 'Subtotal', 'State', ]
                for col_num, header in enumerate(headers):
                    sheet.write(row, col_num, header, format_header)
                row += 1
                row_count = self.write_invoice_data(sheet, format_header, content, row, price, invoices,
                                                    "consumables", total, lang_id)
                row = row_count
                row += 1
        if self.mechanical:
            invoices, total = self._get_mechanical(self.report_selection)
            if invoices and total:
                row += 1
                sheet.merge_range('A' + str(row) + ':J' + str(row), 'Mechanical => Total Amount: ' + str(total), format_header)
                row += 1
                headers = ['Sr.No.', 'Invoice Number', 'Job Card', 'Insurance Company', 'Vehicle Owner', 'Date',
                           'Vehicle Number','Assignees', 'Sales Person', 'Part No', 'Product', 'Qty', 'Cost Price', 'Sale Price', 'Tax Amount', 'Subtotal', 'State', ]
                for col_num, header in enumerate(headers):
                    sheet.write(row, col_num, header, format_header)
                row += 1
                row_count = self.write_invoice_data(sheet, format_header, content, row, price, invoices,
                                                    "mechanical_cog", total, lang_id)
                row = row_count
                row += 1
        if self.sublet:
            invoices, total = self._get_sublet(self.report_selection)
            if invoices and total:
                row += 1
                sheet.merge_range('A' + str(row) + ':J' + str(row), 'Sublet => Total Amount: '+str(total), format_header)
                row += 1
                headers = ['Sr.No.', 'Invoice Number', 'Job Card', 'Insurance Company', 'Vehicle Owner', 'Date',
                           'Vehicle Number','Assignees', 'Sales Person', 'Part No', 'Product', 'Qty', 'Cost Price', 'Sale Price', 'Tax Amount', 'Subtotal', 'State', ]
                for col_num, header in enumerate(headers):
                    sheet.write(row, col_num, header, format_header)
                row += 1
                row_count = self.write_invoice_data(sheet, format_header, content, row, price, invoices,
                                                    "sublet", total, lang_id)
                row = row_count
                row += 1

        # Close and return
        #################################################################
        workbook.close()
        output.seek(0)
        result = base64.b64encode(output.read())

        report_id = self.env['common.xlsx.out'].sudo().create({'filedata': result, 'filename': 'INV.xls'})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=common.xlsx.out&field=filedata&id=%s&filename=%s.xls' % (
                report_id.id, 'Invoice Report.xls'),
            'target': 'new',
        }

        output.close()
