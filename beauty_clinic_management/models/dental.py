# -*- coding: utf-8 -*-

from email.policy import default
from odoo import api, fields, models, _
import datetime
# from mock import DEFAULT
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import hashlib
import time
import pytz


class ClaimManagement(models.Model):
    _name = 'dental.insurance.claim.management'
    _description = 'Beauty Insurance Claim Management'

    claim_date = fields.Date(string='Claim Date')
    name = fields.Many2one('medical.patient', string='Patient')
    insurance_company = fields.Many2one('res.partner', string='Insurance Company',
                                        domain="[('is_insurance_company', '=', True)]")
    insurance_policy_card = fields.Char(string='Insurance Policy Card')
    treatment_done = fields.Boolean(string='Treatment Done')


#     ,domain="[('is_patient', '=', True)]"
class InsurancePlan(models.Model):
    _name = 'medical.insurance.plan'
    _description = "Medical Insurance Plan"

    # @api.depends('name', 'code')
    # def name_get(self):
    #     result = []
    #     for insurance in self:
    #         name = insurance.code + ' ' + insurance.name.name
    #         result.append((insurance.id, name))
    #     return result

    is_default = fields.Boolean(string='Default Plan',
                                help='Check if this is the default plan when assigning this insurance company to a patient')
    name = fields.Char(related='product_insurance_plan_id.name')
    product_insurance_plan_id = fields.Many2one('product.product', string='Plan', required=True,
                                                domain="[('type', '=', 'service'), ('is_insurance_plan', '=', True)]",
                                                help='Insurance company plan')
    company_id = fields.Many2one('res.partner', string='Insurance Company', required=True,
                                 domain="[('is_insurance_company', '=', '1')]")
    notes = fields.Text('Extra info')
    code = fields.Char(required=True, index=True)


class MedicalInsurance(models.Model):
    _name = "medical.insurance"
    _description = "Medical Insurance"
    _rec_name = "name"

    @api.depends('number', 'company_id')
    def name_get(self):
        result = []
        for insurance in self:
            name = insurance.company_id.name + ':' + insurance.number
            result.append((insurance.id, name))
        return result

    name = fields.Char(related="res_partner_insurance_id.name")
    res_partner_insurance_id = fields.Many2one('res.partner', 'Owner')
    number = fields.Char('Number', required=True)
    company_id = fields.Many2one('res.partner', 'Insurance Company', domain="[('is_insurance_company', '=', '1')]",
                                 required=True)
    member_since = fields.Date('Member since')
    member_exp = fields.Date('Expiration date')
    category = fields.Char('Category', help="Insurance company plan / category")
    type = fields.Selection([('state', 'State'), ('labour_union', 'Labour Union / Syndical'), ('private', 'Private'), ],
                            'Insurance Type')
    notes = fields.Text('Extra Info')
    plan_id = fields.Many2one('medical.insurance.plan', 'Plan', help='Insurance company plan')


class Partner(models.Model):
    _inherit = "res.partner"
    _description = "Res Partner"

    date = fields.Date('Partner since', help="Date of activation of the partner or patient")
    alias = fields.Char('alias')
    ref = fields.Char('ID Number')
    is_person = fields.Boolean('Person', help="Check if the partner is a person.")
    is_patient = fields.Boolean('Patient', help="Check if the partner is a patient")
    is_doctor = fields.Boolean('Doctor', help="Check if the partner is a doctor")
    is_institution = fields.Boolean('Institution', help="Check if the partner is a Medical Center")
    is_insurance_company = fields.Boolean('Insurance Company', help="Check if the partner is a Insurance Company")
    is_pharmacy = fields.Boolean('Pharmacy', help="Check if the partner is a Pharmacy")
    middle_name = fields.Char('Middle Name', help="Middle Name")
    lastname = fields.Char('Last Name', help="Last Name")
    insurance_ids = fields.One2many('medical.insurance', 'name', "Insurance")
    treatment_id = fields.Many2many('product.product', 'treatment_insurance_company_relation', 'treatment_id',
                                    'insurance_company_id', 'Treatment')

    _sql_constraints = [
        ('ref_uniq', 'unique (ref)', 'The partner or patient code must be unique')
    ]

    @api.depends('name', 'lastname')
    def name_get(self):
        result = []
        for partner in self:
            name = partner.name
            if partner.middle_name:
                name += ' ' + partner.middle_name
            if partner.lastname:
                name = partner.lastname + ', ' + name
            result.append((partner.id, name))
        return result


class ProductProduct(models.Model):
    # _name = "product.product"
    _description = "Product"
    _inherit = "product.product"

    action_perform = fields.Selection([('action', 'Action'), ('missing', 'Missing'), ('composite', 'Composite')],
                                      'Action perform', default='action')
    is_medicament = fields.Boolean('Medicament', help="Check if the product is a medicament")
    is_insurance_plan = fields.Boolean('Insurance Plan', help='Check if the product is an insurance plan')
    is_treatment = fields.Boolean('Treatment', help="Check if the product is a Treatment")
    is_planned_visit = fields.Boolean('Planned Visit')
    is_material = fields.Boolean('Material')
    duration = fields.Selection(
        [('three_months', 'Three Months'), ('six_months', 'Six Months'), ('one_year', 'One Year')], 'Duration')

    duration_id = fields.Many2one('duration.duration', 'Duration')
    #     insurance_company_ids = fields.One2many('res.partner','treatment_id',string="Insurance Company")
    insurance_company_id = fields.Many2many('res.partner', 'treatment_insurance_company_relation',
                                            'insurance_company_id', 'treatment_id', 'Insurance Company')

    def get_treatment_charge(self):
        return self.lst_price

    def get_operation_names(self, category):
        operations = {}
        product_records = self.env['product.product'].search(
            [('is_treatment', '=', True), ('categ_id.name', '=', category)])
        for each_brw in product_records:
            operations[each_brw.name] = {
                'id': each_brw.id, 'type': each_brw.part_type}
        return operations


class PathologyCategory(models.Model):
    _description = 'Disease Categories'
    _name = 'medical.pathology.category'
    _order = 'parent_id,id'

    @api.depends('name', 'parent_id')
    def name_get(self):
        result = []
        for partner in self:
            name = partner.name
            if partner.parent_id:
                name = partner.parent_id.name + ' / ' + name
            result.append((partner.id, name))
        return result

    @api.model
    def _name_get_fnc(self):
        res = self._name_get_fnc()
        return res

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('Error ! You cannot create a recursive category.'))

    name = fields.Char('Category Name', required=True)
    parent_id = fields.Many2one('medical.pathology.category', 'Parent Category', index=True)
    complete_name = fields.Char(compute='_name_get_fnc', string="Name")
    child_ids = fields.One2many('medical.pathology.category', 'parent_id', 'Children Category')
    active = fields.Boolean('Active', default=True, )


class MedicalPathology(models.Model):
    _name = "medical.pathology"
    _description = "Diseases"

    name = fields.Char('Name', required=True, help="Disease name")
    code = fields.Char('Code', required=True, help="Specific Code for the Disease (eg, ICD-10, SNOMED...)")
    category = fields.Many2one('medical.pathology.category', 'Disease Category')
    chromosome = fields.Char('Affected Chromosome', help="chromosome number")
    protein = fields.Char('Protein involved', help="Name of the protein(s) affected")
    gene = fields.Char('Gene', help="Name of the gene(s) affected")
    info = fields.Text('Extra Info')
    line_ids = fields.One2many('medical.pathology.group.member', 'name',
                               'Groups', help='Specify the groups this pathology belongs. Some'
                                              ' automated processes act upon the code of the group')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'The disease code must be unique')]

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(['|', ('name', operator, name), ('code', operator, name)])
        if not recs:
            recs = self.search([('name', operator, name)])
        return recs.name_get()


class MedicalPathologyGroup(models.Model):
    _description = 'Pathology Group'
    _name = 'medical.pathology.group'

    name = fields.Char('Name', required=True, translate=True, help='Group name')
    code = fields.Char('Code', required=True,
                       help='for example MDG6 code will contain the Millennium Development'
                            ' Goals # 6 diseases : Tuberculosis, Malaria and HIV/AIDS')
    desc = fields.Char('Short Description', required=True)
    info = fields.Text('Detailed information')


class MedicalPathologyGroupMember(models.Model):
    _description = 'Pathology Group Member'
    _name = 'medical.pathology.group.member'

    name = fields.Many2one('medical.pathology', 'Disease', readonly=True)
    disease_group = fields.Many2one('medical.pathology.group', 'Group', required=True)


# TEMPLATE USED IN MEDICATION AND PRESCRIPTION ORDERS

class MedicalMedicationTemplate(models.Model):
    _name = "medical.medication.template"
    _description = "Template for medication"

    medicament = fields.Many2one('medical.medicament', 'Medicament', help="Prescribed Medicament", required=True, )
    indication = fields.Many2one('medical.pathology', 'Indication',
                                 help="Choose a disease for this medicament from the disease list. It can be an existing disease of the patient or a prophylactic.")
    dose = fields.Float('Dose', help="Amount of medication (eg, 250 mg ) each time the patient takes it")
    dose_unit = fields.Many2one('medical.dose.unit', 'dose unit', help="Unit of measure for the medication to be taken")
    route = fields.Many2one('medical.drug.route', 'Administration Route',
                            help="HL7 or other standard drug administration route code.")
    form = fields.Many2one('medical.drug.form', 'Form', help="Drug form, such as tablet or gel")
    qty = fields.Integer('x', default=1, help="Quantity of units (eg, 2 capsules) of the medicament")
    common_dosage = fields.Many2one('medical.medication.dosage', 'Frequency',
                                    help="Common / standard dosage frequency for this medicament")
    frequency = fields.Integer('Frequency',
                               help="Time in between doses the patient must wait (ie, for 1 pill each 8 hours, put here 8 and select 'hours' in the unit field")
    frequency_unit = fields.Selection([
        ('seconds', 'seconds'),
        ('minutes', 'minutes'),
        ('hours', 'hours'),
        ('days', 'days'),
        ('weeks', 'weeks'),
        ('wr', 'when required'),
    ], 'unit', index=True, default='hours')
    admin_times = fields.Char('Admin hours',
                              help='Suggested administration hours. For example, at 08:00, 13:00 and 18:00 can be encoded like 08 13 18')
    duration = fields.Integer('Treatment duration',
                              help="Period that the patient must take the medication. in minutes, hours, days, months, years or indefinately")
    duration_period = fields.Selection(
        [('minutes', 'minutes'), ('hours', 'hours'), ('days', 'days'), ('months', 'months'), ('years', 'years'),
         ('indefinite', 'indefinite')], 'Treatment Period', default='days',
        help="Period that the patient must take the medication. in minutes, hours, days, months, years or indefinately")
    start_treatment = fields.Datetime('Start of treatment', default=fields.Datetime.now)
    end_treatment = fields.Datetime('End of treatment')

    _sql_constraints = [
        ('dates_check', "CHECK (start_treatment < end_treatment)",
         "Treatment Star Date must be before Treatment End Date !"),
    ]


class MedicamentCategory(models.Model):
    _description = 'Medicament Categories'
    _name = 'medicament.category'
    _order = 'parent_id,id'

    @api.depends('name', 'parent_id')
    def name_get(self):
        result = []
        for partner in self:
            name = partner.name
            if partner.parent_id:
                name = partner.parent_id.name + ' / ' + name
            result.append((partner.id, name))
        return result

    @api.model
    def _name_get_fnc(self):
        res = self._name_get_fnc()
        return res

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('Error ! You cannot create a recursive category.'))

    name = fields.Char('Category Name', required=True)
    parent_id = fields.Many2one('medicament.category', 'Parent Category', index=True)
    complete_name = fields.Char(compute='_name_get_fnc', string="Name")
    child_ids = fields.One2many('medicament.category', 'parent_id', 'Children Category')


class MedicalMedicament(models.Model):
    # @api.depends('name')
    # def name_get(self):
    #     result = []
    #     for partner in self:
    #         name = partner.name.name
    #         result.append((partner.id, name))
    #     return result

    _description = 'Medicament'
    _name = "medical.medicament"

    name = fields.Char(related="product_medicament_id.name")
    product_medicament_id = fields.Many2one('product.product', 'Name', required=True,
                                            domain=[('is_medicament', '=', "1")], help="Commercial Name")

    category = fields.Many2one('medicament.category', 'Category')
    active_component = fields.Char('Active component', help="Active Component")
    therapeutic_action = fields.Char('Therapeutic effect', help="Therapeutic action")
    composition = fields.Text('Composition', help="Components")
    indications = fields.Text('Indication', help="Indications")
    dosage = fields.Text('Dosage Instructions', help="Dosage / Indications")
    overdosage = fields.Text('Overdosage', help="Overdosage")
    pregnancy_warning = fields.Boolean('Pregnancy Warning',
                                       help="Check when the drug can not be taken during pregnancy or lactancy")
    pregnancy = fields.Text('Pregnancy and Lactancy', help="Warnings for Pregnant Women")
    presentation = fields.Text('Presentation', help="Packaging")
    adverse_reaction = fields.Text('Adverse Reactions')
    storage = fields.Text('Storage Conditions')
    price = fields.Float(related='product_medicament_id.lst_price', string='Price')
    qty_available = fields.Float(related='product_medicament_id.qty_available', string='Quantity Available')
    notes = fields.Text('Extra Info')
    pregnancy_category = fields.Selection([
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('X', 'X'),
        ('N', 'N'),
    ], 'Pregnancy Category',
        help='** FDA Pregancy Categories ***\n'
             'CATEGORY A :Adequate and well-controlled human studies have failed'
             ' to demonstrate a risk to the fetus in the first trimester of'
             ' pregnancy (and there is no evidence of risk in later'
             ' trimesters).\n\n'
             'CATEGORY B : Animal reproduction studies have failed todemonstrate a'
             ' risk to the fetus and there are no adequate and well-controlled'
             ' studies in pregnant women OR Animal studies have shown an adverse'
             ' effect, but adequate and well-controlled studies in pregnant women'
             ' have failed to demonstrate a risk to the fetus in any'
             ' trimester.\n\n'
             'CATEGORY C : Animal reproduction studies have shown an adverse'
             ' effect on the fetus and there are no adequate and well-controlled'
             ' studies in humans, but potential benefits may warrant use of the'
             ' drug in pregnant women despite potential risks. \n\n '
             'CATEGORY D : There is positive evidence of human fetal  risk based'
             ' on adverse reaction data from investigational or marketing'
             ' experience or studies in humans, but potential benefits may warrant'
             ' use of the drug in pregnant women despite potential risks.\n\n'
             'CATEGORY X : Studies in animals or humans have demonstrated fetal'
             ' abnormalities and/or there is positive evidence of human fetal risk'
             ' based on adverse reaction data from investigational or marketing'
             ' experience, and the risks involved in use of the drug in pregnant'
             ' women clearly outweigh potential benefits.\n\n'
             'CATEGORY N : Not yet classified')


class MedicalSpeciality(models.Model):
    _name = "medical.speciality"
    _description = "Medical Speciality"

    name = fields.Char('Description', required=True, help="ie, Addiction Psychiatry")
    code = fields.Char('Code', help="ie, ADP")

    _sql_constraints = [
        ('code_uniq', 'unique (name)', 'The Medical Specialty code must be unique')]


class MedicalPhysician(models.Model):
    _name = "medical.physician"
    _description = "Information about the doctor"

    # @api.depends('name')
    # def name_get(self):
    #     result = []
    #     for partner in self:
    #         name = partner.name.name
    #         result.append((partner.id, name))
    #     return result
    name = fields.Char(related='res_partner_medical_physician_id.name')
    res_partner_medical_physician_id = fields.Many2one('res.partner', 'Physician', required=True,
                                                       domain=[('is_doctor', '=', "1"), ('is_person', '=', "1")],
                                                       help="Physician's Name, from the partner list")
    institution = fields.Many2one('res.partner', 'Institution', domain=[('is_institution', '=', "1")],
                                  help="Institution where she/he works")
    code = fields.Char('ID', help="MD License ID")
    speciality = fields.Many2one('medical.speciality', 'Specialty', required=True, help="Specialty Code")
    info = fields.Text('Extra info')
    user_id = fields.Many2one('res.users', related='res_partner_medical_physician_id.user_id', string='Physician User',
                              store=True)
    slot_ids = fields.One2many('doctor.slot', 'doctor_id', 'Availabilities', copy=True)
    active = fields.Boolean('Archive', default=True)
    active_code = fields.Char('ID', default='Test', compute='doctor_active', store=True)

    @api.depends('active_code', 'active')
    def doctor_active(self):
        for record in self:
            if record.active_code:
                if record.active_code and record.active == False:
                    doctor_id = self.env['medical.appointment'].sudo().search(
                        [('doctor.name', '=', record.name), ('active', '=', True)])
                    for doc in doctor_id:
                        doc.write({'active': False})
                if record.active_code and record.active == True:
                    doctor_id = self.env['medical.appointment'].sudo().search(
                        [('doctor.name', '=', record.name), ('active', '=', False)])
                    for doc in doctor_id:
                        doc.write({'active': True})


class MedicalFamilyCode(models.Model):
    _name = "medical.family_code"
    _description = "Medical Family Code"
    # _rec_name = "name"

    name = fields.Char(related="res_partner_family_medical_id.name")
    res_partner_family_medical_id = fields.Many2one('res.partner', 'Name', required=True,
                                                    help="Family code within an operational sector")
    members_ids = fields.Many2many('res.partner', 'family_members_rel', 'family_id', 'members_id', 'Members',
                                   domain=[('is_person', '=', "1")])
    info = fields.Text('Extra Information')

    _sql_constraints = [('code_uniq', 'unique (res_partner_family_medical_id)', 'The Family code name must be unique')]


class MedicalOccupation(models.Model):
    _name = "medical.occupation"
    _description = "Occupation / Job"

    name = fields.Char('Occupation', required=True)
    code = fields.Char('Code')

    _sql_constraints = [
        ('occupation_name_uniq', 'unique(name)', 'The Name must be unique !'),
    ]


class AccountInvoice(models.Model):
    _inherit = "account.move"
    _description = "Account Invoice"

    dentist = fields.Many2one('medical.physician', 'Doctor')
    patient = fields.Many2one('medical.patient')
    insurance_company = fields.Many2one('res.partner', 'Insurance Company',
                                        domain=[('is_insurance_company', '=', True)])

    @api.onchange('partner_id')
    def partneronchange(self):
        if (self.partner_id and self.partner_id.is_patient):
            patient_id = self.env['medical.patient'].search([('partner_id', '=', self.partner_id.id)])
            self.patient = patient_id.id
        else:
            self.patient = False


class website(models.Model):
    _inherit = 'website'
    _description = "Website"

    def get_image(self, a):
        #         if 'image' in a.keys():
        if 'image' in list(a.keys()):
            return True
        else:
            return False

    def get_type(self, record1):
        categ_type = record1['type']
        categ_ids = self.env['product.category'].search([('name', '=', categ_type)])
        if categ_ids['type'] == 'view':
            return False
        return True

    def check_next_image(self, main_record, sub_record):
        if len(main_record['image']) > sub_record:
            return 1
        else:
            return 0

    def image_url_new(self, record1):
        """Returns a local url that points to the image field of a given browse record."""
        lst = []
        size = None
        field = 'datas'
        record = self.env['ir.attachment'].browse(self.ids)
        cnt = 0
        for r in record:
            if r.store_fname:
                cnt = cnt + 1
                model = r._name
                sudo_record = r.sudo()
                id = '%s_%s' % (r.id, hashlib.sha1(
                    (str(sudo_record.write_date) or str(sudo_record.create_date) or '').encode('utf-8')).hexdigest()[
                                      0:7])
                if cnt == 1:
                    size = '' if size is None else '/%s' % size
                else:
                    size = '' if size is None else '%s' % size
                lst.append('/website/image/%s/%s/%s%s' % (model, id, field, size))
        return lst


# PATIENT GENERAL INFORMATION

class MedicalPatient(models.Model):

    @api.depends('partner_id', 'patient_id')
    def name_get(self):
        result = []
        for partner in self:
            name = partner.partner_id.name
            if partner.patient_id:
                name = '[' + partner.patient_id + ']' + name
            result.append((partner.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(['|', '|', '|', '|', '|', ('partner_id', operator, name), ('patient_id', operator, name),
                                ('mobile', operator, name), ('other_mobile', operator, name),
                                ('lastname', operator, name), ('middle_name', operator, name)])
        if not recs:
            recs = self.search([('partner_id', operator, name)])
        return recs.name_get()

    @api.onchange('dob')
    def onchange_dob(self):
        c_date = datetime.today().strftime('%Y-%m-%d')
        if self.dob:
            if not (str(self.dob) <= c_date):
                raise UserError(_('Birthdate cannot be After Current Date.'))
        return {}

    # @api.onchange('mobile')
    # def onchange_mobile(self):
    #     if self.mobile:
    #         patients = self.env['medical.patient'].search([('mobile', '=', self.mobile)])
    #         if patients:
    #             raise UserError(_('Birthdate cannot be After Current Date.'))
    #     return {}

    # Automatically assign the family code

    @api.onchange('partner_id')
    def onchange_partnerid(self):
        family_code_id = ""
        if self.partner_id:
            self._cr.execute('select family_id from family_members_rel where members_id=%s limit 1',
                             (self.partner_id.id,))
            a = self._cr.fetchone()
            if a:
                family_code_id = a[0]
            else:
                family_code_id = ''
        self.family_code = family_code_id

    # Get the patient age in the following format : "YEARS MONTHS DAYS"
    # It will calculate the age of the patient while the patient is alive. When the patient dies, it will show the age at time of death.

    def _patient_age(self):
        def compute_age_from_dates(patient_dob, patient_deceased, patient_dod):
            now = datetime.now()
            if (patient_dob):
                dob = datetime.strptime(str(patient_dob), '%Y-%m-%d')
                if patient_deceased:
                    dod = datetime.strptime(str(patient_dod), '%Y-%m-%d %H:%M:%S')
                    delta = relativedelta(dod, dob)
                    deceased = " (deceased)"
                else:
                    delta = relativedelta(now, dob)
                    deceased = ''
                years_months_days = str(delta.years) + "y " + str(delta.months) + "m " + str(
                    delta.days) + "d" + deceased
            else:
                years_months_days = "No DoB !"

            return years_months_days

        for rec in self:
            rec.age = compute_age_from_dates(rec.dob, rec.deceased, rec.dod)

    @api.depends_context('critical_info_fun')
    def _medical_alert(self):
        for patient_data in self:
            medical_alert = ''

            if patient_data.medicine_yes:
                medical_alert += patient_data.medicine_yes + '\n'
            if patient_data.card_yes:
                medical_alert += patient_data.card_yes + '\n'
            if patient_data.allergies_yes:
                medical_alert += patient_data.allergies_yes + '\n'
            if patient_data.attacks_yes:
                medical_alert += patient_data.attacks_yes + '\n'
            if patient_data.heart_yes:
                medical_alert += patient_data.heart_yes + '\n'
            if patient_data.bleeding_yes:
                medical_alert += patient_data.bleeding_yes + '\n'
            if patient_data.infectious_yes:
                medical_alert += patient_data.infectious_yes + '\n'
            if patient_data.reaction_yes:
                medical_alert += patient_data.reaction_yes + '\n'
            if patient_data.surgery_yes:
                medical_alert += patient_data.surgery_yes + '\n'
            if patient_data.pregnant_yes:
                medical_alert += patient_data.pregnant_yes + '\n'
            patient_data.critical_info_fun = medical_alert
            if not patient_data.critical_info:
                patient_data.critical_info = medical_alert

    _name = "medical.patient"
    _description = "Patient related information"
    _rec_name = "partner_id"

    partner_id = fields.Many2one('res.partner', 'Patient', required="1",
                                 domain=[('is_patient', '=', True), ('is_person', '=', True)], help="Patient Name")
    patient_id = fields.Char('Patient ID',
                             help="Patient Identifier provided by the Health Center. Is not the patient id from the partner form",
                             default=lambda self: _('New'))
    ssn = fields.Char('SSN', help="Patient Unique Identification Number")
    lastname = fields.Char(related='partner_id.lastname', string='Lastname')
    middle_name = fields.Char(related='partner_id.middle_name', string='Middle Name')
    family_code = fields.Many2one('medical.family_code', 'Family', help="Family Code")
    identifier = fields.Char(string='SSN', related='partner_id.ref', help="Social Security Number or National ID")
    current_insurance = fields.Many2one('medical.insurance', "Insurance",
                                        help="Insurance information. You may choose from the different insurances belonging to the patient")
    sec_insurance = fields.Many2one('medical.insurance', "Insurance", domain="[('partner_id','=',partner_id)]",
                                    help="Insurance information. You may choose from the different insurances belonging to the patient")
    dob = fields.Date('Date of Birth')
    age = fields.Char(compute='_patient_age', string='Patient Age',
                      help="It shows the age of the patient in years(y), months(m) and days(d).\nIf the patient has died, the age shown is the age at time of death, the age corresponding to the date on the death certificate. It will show also \"deceased\" on the field")
    sex = fields.Selection([('m', 'Male'), ('f', 'Female'), ], 'Sex', )
    marital_status = fields.Selection(
        [('s', 'Single'), ('m', 'Married'), ('w', 'Widowed'), ('d', 'Divorced'), ('x', 'Separated'), ],
        'Marital Status')
    blood_type = fields.Selection([('A', 'A'), ('B', 'B'), ('AB', 'AB'), ('O', 'O'), ], 'Blood Type')
    rh = fields.Selection([('+', '+'), ('-', '-'), ], 'Rh')
    user_id = fields.Many2one('res.users', related='partner_id.user_id', string='Doctor',
                              help="Physician that logs in the local Medical system (HIS), on the health center. It doesn't necesarily has do be the same as the Primary Care doctor",
                              store=True)
    medications = fields.One2many('medical.patient.medication', 'name', 'Medications')
    prescriptions = fields.One2many('medical.prescription.order', 'name', "Prescriptions")
    diseases_ids = fields.One2many('medical.patient.disease', 'name', 'Diseases')
    critical_info = fields.Text(compute='_medical_alert', string='Medical Alert',
                                help="Write any important information on the patient's disease, surgeries, allergies, ...")
    medical_history = fields.Text('Medical History')
    critical_info_fun = fields.Text(compute='_medical_alert', string='Medical Alert',
                                    help="Write any important information on the patient's disease, surgeries, allergies, ...")
    medical_history_fun = fields.Text('Medical History')
    general_info = fields.Text('General Information', help="General information about the patient")
    deceased = fields.Boolean('Deceased', help="Mark if the patient has died")
    dod = fields.Datetime('Date of Death')
    apt_id = fields.Many2many('medical.appointment', 'pat_apt_rel', 'patient', 'apid', 'Appointments')
    attachment_ids = fields.One2many('ir.attachment', 'patient_id', 'attachments')
    photo = fields.Binary(related='partner_id.image_1024', string='photos', store=True, readonly=False)
    report_date = fields.Date("Report Date:", default=fields.Datetime.to_string(fields.Datetime.now()))
    occupation_id = fields.Many2one('medical.occupation', 'Occupation')
    primary_doctor_id = fields.Many2one('medical.physician', 'Primary Doctor', )
    referring_doctor_id = fields.Many2one('medical.physician', 'Referring  Doctor', )
    note = fields.Text('Notes', help="Notes and To-Do")
    mobile = fields.Char('Mobile')
    other_mobile = fields.Char('Other Mobile')
    teeth_treatment_ids = fields.One2many('medical.teeth.treatment', 'patient_id', 'Operations', readonly=True)
    nationality_id = fields.Many2one('patient.nationality', 'Nationality')
    patient_complaint_ids = fields.One2many('patient.complaint', 'patient_id')
    receiving_treatment = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                           '1. Are you currently receiving treatment from a doctor hospital or clinic ?')
    receiving_medicine = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                          '2. Are you currently taking any prescribed medicines(tablets, inhalers, contraceptive or hormone) ?')
    medicine_yes = fields.Char('Note')
    have_card = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ], '3. Are you carrying a medical warning card ?')
    card_yes = fields.Char('Note')
    have_allergies = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                      '4. Do you suffer from any allergies to any medicines (penicillin) or substances (rubber / latex or food) ?')
    allergies_yes = fields.Char('Note')
    have_feaver = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ], '5. Do you suffer from hay fever or eczema ?')
    have_ashtham = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                    '6. Do you suffer from bronchitis, asthma or other chest conditions ?')
    have_attacks = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                    '7. Do you suffer from fainting attacks, giddlness, blackouts or epllepsy ?')
    attacks_yes = fields.Char('Note')
    have_heart = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                  '8. Do you suffer from heart problems, angina, blood pressure problems, or stroke ?')
    heart_yes = fields.Char('Note')
    have_diabetic = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                     '9. Are you diabetic(or is anyone in your family) ?')
    have_arthritis = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ], '10. Do you suffer from arthritis ?')
    have_bleeding = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                     '11. Do you suffer from bruising or persistent bleeding following injury, tooth extraction or surgery ?')
    bleeding_yes = fields.Char('Note')
    have_infectious = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                       '12. Do you suffer from any infectious disease (including HIV and Hepatitis) ?')
    infectious_yes = fields.Char('Note')
    have_rheumatic = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                      '13. Have you ever had rheumatic fever or chorea ?')
    have_liver = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                  '14. Have you ever had liver disease (e.g jundice, hepatitis) or kidney disease ?')
    have_serious = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                    '15. Have you ever had any other serious illness ?')
    have_reaction = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                     '16. Have you ever had a bad reaction to general or local anaesthetic ?')
    reaction_yes = fields.Char('Note')
    have_surgery = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ], '17. Have you ever had heart surgery ?')
    surgery_yes = fields.Char('Note')
    have_tabacco = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                    '18. Do you smoke any tabacco products now (or in the past ) ?')
    have_gutkha = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                   '19. Do you chew tabacco, pan, use gutkha or supari now (or in the past) ?')
    have_medicine = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ],
                                     '20. Is there any other information which your dentist might need to know about, such as self-prescribe medicine (eg. aspirin) ?')
    have_pregnant = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ], '21. Are you currently pregnant ?')
    pregnant_yes = fields.Char('Note')
    have_breastfeeding = fields.Selection([('YES', 'YES'), ('NO', 'NO'), ], '22. Are you currently breastfeeding ?')
    updated_date = fields.Date('Updated Date')
    arebic = fields.Boolean('Arabic')
    invoice_count = fields.Integer(compute='compute_count')
    active = fields.Boolean(default="True")
    block_reason = fields.Text('Reason')
    civil_id = fields.Char('Civil Id')
    family_link = fields.Boolean('Family Link')
    link_partner_id = fields.Many2one('medical.patient', 'Link Partner')

    def blockpatient(self):
        self.active = False
        return {
            'name': _('Block'),
            'view_mode': 'form',
            'res_model': 'block.reason',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_id': self.env.ref('beauty_clinic_management.block_reason_wizard').id,
            'context': {'default_patient_id': self.id},
        }

    def unblockpatient(self):
        self.active = True

    def get_user_name(self):
        get_doctor_id = self.env['medical.appointment'].search([('patient', '=', self.id)], limit=1)
        return get_doctor_id.doctor.name

    def compute_count(self):
        for record in self:
            record.invoice_count = self.env['account.move'].search_count(
                [('partner_id', '=', record.partner_id.id), ('move_type', '!=', 'entry')])

    _sql_constraints = [
        ('name_uniq', 'unique (partner_id)', 'The Patient already exists'),
        ('patient_id_uniq', 'unique (patient_id)', 'The Patient ID already exists'),
        ('mobile_number_uniq', 'CHECK(1=1)', 'This Mobile Number already exists'), ]

    def get_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'domain': [('partner_id', '=', self.partner_id.id), ('move_type', '!=', 'entry')],
            'context': "{'create': False}"
        }

    def get_img(self):
        for rec in self:
            res = {}
            img_lst_ids = []
            imd = self.env['ir.model.data']
            action_view_id = imd.xmlid_to_res_id('action_result_image_view')
            for i in rec.attachment_ids:
                img_lst_ids.append(i.id)
            res['image'] = img_lst_ids
            return {
                'type': 'ir.actions.client',
                'name': 'Result Images',
                'tag': 'result_images',
                'params': {
                    'patient_id': rec.id or False,
                    'model': 'medical.patient',
                    'values': res
                },
            }

    def get_patient_history(self, appt_id):
        return_list = [];
        extra_history = 0;
        total_operation = [];
        return_list.append([])
        if appt_id:
            appt_id_brw = self.env['medical.appointment'].browse(appt_id)
            total_operation = appt_id_brw.operations
            extra_history = len(total_operation)
            for each_patient_operation in self.teeth_treatment_ids:
                if each_patient_operation.description.action_perform == "missing" and each_patient_operation.appt_id.id < appt_id:
                    total_operation += each_patient_operation
        else:
            total_operation = self.teeth_treatment_ids
            extra_history = len(total_operation)
        history_count = 0
        for each_operation in total_operation:
            history_count += 1
            current_tooth_id = each_operation.teeth_id.internal_id
            if each_operation.description:
                desc_brw = self.env['product.product'].browse(each_operation.description.id)
                if desc_brw.action_perform == 'missing':
                    return_list[0].append(current_tooth_id)
                self._cr.execute('select teeth from teeth_code_medical_teeth_treatment_rel where operation = %s' % (
                    each_operation.id,))
                multiple_teeth = self._cr.fetchall()
                multiple_teeth_list = [multiple_teeth_each[0] for multiple_teeth_each in multiple_teeth]
                total_multiple_teeth_list = []
                for each_multiple_teeth_list in multiple_teeth_list:
                    each_multiple_teeth_list_brw = self.env['teeth.code'].browse(each_multiple_teeth_list)
                    total_multiple_teeth_list.append(each_multiple_teeth_list_brw.internal_id)
                    multiple_teeth_list = total_multiple_teeth_list
                other_history = 0
                if history_count > extra_history:
                    other_history = 1
                return_list.append({'other_history': other_history, 'created_date': each_operation.create_date,
                                    'status': each_operation.state, 'multiple_teeth': multiple_teeth_list,
                                    'tooth_id': current_tooth_id, 'surface': each_operation.detail_description,
                                    'desc': {'name': each_operation.description.name,
                                             'id': each_operation.description.id,
                                             'action': each_operation.description.action_perform}})
        return return_list

    def create_lines(self, treatment_lines, patient_id, appt_id):
        # create objects
        medical_teeth_treatment_obj = self.env['medical.teeth.treatment']
        medical_physician_obj = self.env['medical.physician']
        product_obj = self.env['product.product']
        teeth_code_obj = self.env['teeth.code']
        # delete previous records
        patient = int(patient_id)
        patient_brw = self.env['medical.patient'].browse(patient)
        partner_brw = patient_brw.partner_id
        if appt_id:
            prev_appt_operations = medical_teeth_treatment_obj.search(
                [('appt_id', '=', int(appt_id)), ('state', '!=', 'completed')])
            prev_appt_operations.unlink()
        else:
            prev_pat_operations = medical_teeth_treatment_obj.search(
                [('patient_id', '=', int(patient_id)), ('state', '!=', 'completed')])
            prev_pat_operations.unlink()

        prev_pat_missing_operations = medical_teeth_treatment_obj.search(
            [('patient_id', '=', int(patient_id)), ('state', '!=', 'completed')])
        for each_prev_pat_missing_operations in prev_pat_missing_operations:
            if each_prev_pat_missing_operations.description.action_perform == 'missing':
                each_prev_pat_missing_operations.unlink()
        if treatment_lines:
            current_physician = 0;
            for each in treatment_lines:
                if each.get('prev_record') == 'false':
                    all_treatment = each.get('values')
                    if all_treatment:
                        for each_trt in all_treatment:

                            vals = {}
                            category_id = int(each_trt.get('categ_id'))
                            vals['description'] = category_id
                            if 1:
                                if (str(each.get('teeth_id')) != 'all'):
                                    actual_teeth_id = teeth_code_obj.search(
                                        [('internal_id', '=', int(each.get('teeth_id')))])
                                    vals['teeth_id'] = actual_teeth_id[0].id
                                vals['patient_id'] = patient
                                desc = ''
                                for each_val in each_trt['values']:
                                    if each_val:
                                        desc += each_val + ' '
                                vals['detail_description'] = desc.rstrip()
                                dentist = each.get('dentist')
                                if dentist:
                                    physician = medical_physician_obj.search([('name', '=', dentist)])
                                    if physician:
                                        dentist = physician.id
                                        vals['dentist'] = dentist
                                        current_physician = 1
                                status = ''
                                if each.get('status_name') and each.get('status_name') != 'false':
                                    status_name = each.get('status_name')
                                    status = (str(each.get('status_name')))
                                    if status_name == 'in_progress':
                                        status = 'in_progress'
                                    elif status_name == 'planned':
                                        status = 'planned'
                                else:
                                    status = 'planned'
                                vals['state'] = status
                                p_brw = product_obj.browse(vals['description'])
                                vals['amount'] = p_brw.lst_price
                                if appt_id:
                                    vals['appt_id'] = appt_id
                                treatment_id = medical_teeth_treatment_obj.create(vals);
                                if each.get('multiple_teeth'):
                                    full_mouth = each.get('multiple_teeth');
                                    full_mouth = full_mouth.split('_')
                                    operate_on_tooth = []
                                    for each_teeth_from_full_mouth in full_mouth:
                                        actual_teeth_id = teeth_code_obj.search(
                                            [('internal_id', '=', int(each_teeth_from_full_mouth))])
                                        operate_on_tooth.append(actual_teeth_id.id)
                                    treatment_id.write({'teeth_code_rel': [(6, 0, operate_on_tooth)]})

            #                                         cr.execute('insert into teeth_code_medical_teeth_treatment_rel(operation,teeth) values(%s,%s)' % (treatment_id,each_teeth_from_full_mouth))
            invoice_vals = {}
            invoice_line_vals = []
            # Creating invoice lines
            # get account id for products
            jr_search = self.env['account.journal'].search([('type', '=', 'sale')])
            jr_brw = jr_search
            for each in treatment_lines:
                if each.get('prev_record') == 'false':
                    if str(each.get('status_name')).lower() == 'completed':
                        for each_val in each['values']:
                            each_line = [0, False]
                            product_dict = {}
                            product_dict['product_id'] = int(each_val['categ_id'])
                            p_brw = product_obj.browse(int(each_val['categ_id']))
                            if p_brw.action_perform != 'missing':
                                desc = ''
                                features = ''
                                for each_v in each_val['values']:
                                    if each_v:
                                        desc = str(each_v)
                                        features += desc + ' '
                                if (each['teeth_id'] != 'all'):
                                    actual_teeth_id = teeth_code_obj.search(
                                        [('internal_id', '=', int(each.get('teeth_id')))])
                                    invoice_name = actual_teeth_id.name_get()
                                    product_dict['name'] = str(invoice_name[0][1]) + ' ' + features
                                else:
                                    product_dict['name'] = 'Full Mouth'
                                product_dict['quantity'] = 1
                                product_dict['price_unit'] = p_brw.lst_price
                                acc_obj = self.env['account.account'].search(
                                    [('name', '=', 'Local Sales'), ('user_type_id', '=', 'Income')], limit=1)
                                for account_id in jr_brw:
                                    product_dict[
                                        'account_id'] = account_id.payment_debit_account_id.id if account_id.payment_debit_account_id else acc_obj.id
                                each_line.append(product_dict)
                                invoice_line_vals.append(each_line)
                            # Creating invoice dictionary
                            # invoice_vals['account_id'] = partner_brw.property_account_receivable_id.id
                            if patient_brw.current_insurance:
                                invoice_vals['partner_id'] = patient_brw.current_insurance.company_id.id
                            else:
                                invoice_vals['partner_id'] = partner_brw.id
                            invoice_vals['patient_id'] = partner_brw.id
                            # invoice_vals['partner_id'] = partner_brw.id
                            if current_physician:
                                invoice_vals['dentist'] = physician[0].id
                            invoice_vals['move_type'] = 'out_invoice'
                            invoice_vals['insurance_company'] = patient_brw.current_insurance.company_id.id
                            invoice_vals['invoice_line_ids'] = invoice_line_vals

            # creating account invoice
            if invoice_vals:
                self.env['account.move'].create(invoice_vals)
        else:
            return False

    def get_back_address(self, active_patient):
        active_patient = str(active_patient)
        action_rec = self.env['ir.actions.act_window'].search([('res_model', '=', 'medical.patient')])
        action_id = str(action_rec.id)
        address = '/web#id=' + active_patient + '&view_type=form&model=medical.patient&action=' + action_id
        return address

    def get_date(self, date1, lang):
        new_date = ''
        if date1:
            search_id = self.env['res.lang'].search([('code', '=', lang)])
            new_date = datetime.strftime(datetime.strptime(date1, '%Y-%m-%d %H:%M:%S').date(), search_id.date_format)
        return new_date

    def write(self, vals):
        if 'critical_info' in list(vals.keys()):
            #         if 'critical_info' in vals.keys():
            vals['critical_info_fun'] = vals['critical_info']
        #         elif 'critical_info_fun' in vals.keys():
        elif 'critical_info_fun' in list(vals.keys()):
            vals['critical_info'] = vals['critical_info_fun']
        #         if 'medical_history' in vals.keys():
        if 'medical_history' in list(vals.keys()):
            vals['medical_history_fun'] = vals['medical_history']
        #         elif 'medical_history_fun' in vals.keys():
        elif 'medical_history_fun' in list(vals.keys()):
            vals['medical_history'] = vals['medical_history_fun']
        res = super(MedicalPatient, self).write(vals)
        if vals.get('mobile'):
            list_id = [self.id]
            if self.link_partner_id:
                if self.link_partner_id.mobile == vals.get('mobile'):
                    pass
                else:
                    list_id.append(self.link_partner_id.id)
                    patients = self.env["medical.patient"].search(
                        [('mobile', '=', vals.get('mobile')), ('id', 'not in', list_id)])
                    if patients:
                        raise ValidationError(_('This Mobile Number already exists.'))
            else:
                patients = self.env["medical.patient"].search(
                    [('mobile', '=', vals.get('mobile')), ('id', 'not in', list_id)])
                if patients:
                    raise ValidationError(_('This Mobile Number already exists.'))
        return res

    @api.model
    def create(self, vals):
        if vals.get('critical_info'):
            vals['critical_info_fun'] = vals['critical_info']
        elif vals.get('critical_info_fun'):
            vals['critical_info'] = vals['critical_info_fun']
        if vals.get('medical_history'):
            vals['medical_history_fun'] = vals['medical_history']
        elif vals.get('medical_history_fun'):
            vals['medical_history'] = vals['medical_history_fun']
        c_date = datetime.today().strftime('%Y-%m-%d')
        result = False
        # if vals.get('patient_id', 'New') == 'New':
        #     vals['patient_id'] = self.env['ir.sequence'].next_by_code('medical.patient') or 'New'
        if 'dob' in vals and vals.get('dob'):
            if (vals['dob'] > c_date):
                raise ValidationError(_('Birthdate cannot be After Current Date.'))

        result = super(MedicalPatient, self).create(vals)
        if vals.get('mobile'):
            list_id = [result.id]
            if result.link_partner_id:
                if result.link_partner_id.mobile == vals.get('mobile'):
                    pass
                else:
                    list_id.append(result.link_partner_id.id)
                    patients = self.env["medical.patient"].search(
                        [('mobile', '=', vals.get('mobile')), ('id', 'not in', list_id)])
                    if patients:
                        raise ValidationError(_('This Mobile Number already exists.'))
            else:
                patients = self.env["medical.patient"].search(
                    [('mobile', '=', vals.get('mobile')), ('id', 'not in', list_id)])
                if patients:
                    raise ValidationError(_('This Mobile Number already exists.'))

        if vals.get('patient_id', 'New') == 'New':
            result.patient_id = self.env['ir.sequence'].next_by_code('medical.patient') or 'New'

        return result

    #
    #     def get_img(self):
    #         for rec in self:
    #             res = {}
    #             img_lst_ids = []
    #             imd = self.env['ir.model.data']
    #             action_view_id = imd.xmlid_to_res_id('action_result_image_view')
    #             for i in rec.attachment_ids:
    #                 img_lst_ids.append(i.id)
    #             res['image'] = img_lst_ids
    #
    #             return {
    #             'type': 'ir.actions.client',
    #             'name': 'Patient image',
    #             'tag': 'result_images',
    #             'params': {
    #                'patient_id':  rec.id  or False,
    #                'model':  'medical.patient',
    #                'values': res
    #             },
    #         }

    def open_chart(self):
        for rec in self:
            appt_id = self.env['medical.appointment'].search([
                ('state', 'not in', ['done', 'cancel']),
                ('patient', '=', self.id),
            ], order='id DESC', limit=1)
            if not appt_id:
                raise UserError(
                    _('Currently no running any appointment for %s!\n Please create the appointment for %s') % (
                    self.partner_id.name, self.partner_id.name))
            appt_id = appt_id.id
            context = dict(self._context or {})

            #             if 'appointment_id_new' in context.keys():
            if 'appointment_id_new' in list(context.keys()):
                appt_id = context['appointment_id_new']
            if context is None:
                context = {}
            imd = self.env['ir.model.data']
            action_view_id = self.env['ir.model.data']._xmlid_to_res_id('action_open_human_body_chart')
            # action_view_id = imd.xmlid_to_res_id('action_open_human_body_chart')
            teeth_obj = self.env['chart.selection'].search([])
            teeth = teeth_obj[-1]
            res_open_chart = {
                'type': 'ir.actions.client',
                'name': 'Human Body Chart',
                'tag': 'human_body_chart',
                'params': {
                    'patient_id': rec.id or False,
                    'appt_id': appt_id,
                    'model': 'medical.patient',
                    'type': teeth.type,
                    'dentist': rec.referring_doctor_id.id
                },
            }
            return res_open_chart

    def close_chart(self):
        res_close_chart = {'type': 'ir.actions.client', 'tag': 'history_back'}
        return res_close_chart

    @api.model
    def _create_birthday_scheduler(self):
        self.create_birthday_scheduler()

    @api.model
    def create_birthday_scheduler(self):
        #         alert_id = self.pool.get('ir.cron').search(cr, uid, [('model', '=', 'medical.patient'), ('function', '=', 'create_birthday_scheduler')])
        #         alert_record = self.pool.get('ir.cron').browse(cr, uid, alert_id[0], context=context)
        #         alert_date = datetime.strptime(alert_record.nextcall, "%Y-%m-%d %H:%M:%S").date()
        alert_date1 = datetime.today().strftime('%Y-%m-%d')
        alert_date = datetime.strptime(str(alert_date1), "%Y-%m-%d")
        patient_ids = self.search([])
        for each_id in patient_ids:
            birthday_alert_id = self.env['patient.birthday.alert'].search([('patient_id', '=', each_id.id)])
            if not birthday_alert_id:
                if each_id.dob:
                    dob = datetime.strptime(str(each_id.dob), "%Y-%m-%d")
                    if dob.day <= alert_date.day or dob.month <= alert_date.month or dob.year <= alert_date.year:
                        self.env['patient.birthday.alert'].create({'patient_id': each_id.id,
                                                                   'dob': dob,
                                                                   'date_create': datetime.today().strftime(
                                                                       '%Y-%m-%d')})

        return True

    @api.model
    def _create_planned_visit_scheduler(self):
        self.create_planned_visit_scheduler()

    @api.model
    def create_planned_visit_scheduler(self):
        patient_ids = self.search([])
        patient_dict_sent = []
        patient_dict_not_sent = []
        flag1 = 0
        flag2 = 0
        for each_id in patient_ids:
            for service_id in each_id.teeth_treatment_ids:
                if service_id.state == 'completed':
                    if service_id.description.is_planned_visit:
                        create_date_obj = service_id.create_date
                        if service_id.description.duration == 'three_months':
                            check_date = (datetime.now().date() - timedelta(3 * 365 / 12)).isoformat()
                        elif service_id.description.duration == 'six_months':
                            check_date = (datetime.now().date() - timedelta(6 * 365 / 12)).isoformat()
                        elif service_id.description.duration == 'one_year':
                            check_date = (datetime.now().date() - timedelta(12 * 365 / 12)).isoformat()

                        if str(create_date_obj)[0:10] < check_date:
                            flag1 = 0
                            for each_pat in patient_dict_sent:
                                if each_pat['patient_id'] == each_id.id and each_pat[
                                    'product_id'] == service_id.description.id:
                                    flag1 = 1
                                    if str(service_id.create_date)[0:10] > each_pat['date']:
                                        each_pat['date'] = str(service_id.create_date)[0:10]
                                    break
                            if flag1 == 0:
                                patient_dict_sent.append({'patient_id': each_id.id, 'name': each_id.name.name,
                                                          'product_id': service_id.description.id,
                                                          'pname': service_id.description.name,
                                                          'date': str(service_id.create_date)[0:10]})
                        else:
                            flag2 = 0
                            for each_pat in patient_dict_not_sent:
                                if each_pat['patient_id'] == each_id.id and each_pat[
                                    'product_id'] == service_id.description.id:
                                    flag2 = 1
                                    if str(service_id.create_date)[0:10] > each_pat['date']:
                                        each_pat['date'] = str(service_id.create_date)[0:10]
                                    break

                            if flag2 == 0:
                                patient_dict_not_sent.append({'patient_id': each_id.id, 'name': each_id.partner_id.name,
                                                              'product_id': service_id.description.id,
                                                              'pname': service_id.description.name,
                                                              'date': str(service_id.create_date)[0:10]})
        for each_not_sent in patient_dict_not_sent:
            for each_sent in patient_dict_sent:
                if each_sent['patient_id'] == each_not_sent['patient_id'] and each_sent['product_id'] == each_not_sent[
                    'product_id']:
                    patient_dict_sent.remove(each_sent)
                    break
        palnned_obj = self.env['planned.visit.alert']
        visit_ids = palnned_obj.search([])
        for each in patient_dict_not_sent:
            flag3 = 0
            for each_record in visit_ids:
                if each_record.patient_name.id == each['patient_id'] and each_record.treatment_name.id == each[
                    'product_id']:
                    flag3 = 1
                    break
            if flag3 == 0:
                palnned_obj.create({'patient_name': each['patient_id'],
                                    'treatment_name': each['product_id'], 'operated_date': each['date']})

        return True


class PatientNationality(models.Model):
    _name = "patient.nationality"
    _description = "Patient Nationality"

    name = fields.Char('Name', required=True)
    code = fields.Char('Code')


class MedicalPatientDisease(models.Model):

    @api.depends('pathology')
    def name_get(self):
        result = []
        for disease in self:
            name = disease.pathology.name
            result.append((disease.id, name))
        return result

    _name = "medical.patient.disease"
    _description = "Disease info"
    _order = 'is_active desc, disease_severity desc, is_infectious desc, is_allergy desc, diagnosed_date desc'

    name = fields.Many2one('medical.patient', 'Patient ID', readonly=True)
    pathology = fields.Many2one('medical.pathology', 'Disease', required=True, help="Disease")
    disease_severity = fields.Selection([('1_mi', 'Mild'), ('2_mo', 'Moderate'), ('3_sv', 'Severe'), ], 'Severity',
                                        index=True)
    is_on_treatment = fields.Boolean('Currently on Treatment')
    is_infectious = fields.Boolean('Infectious Disease',
                                   help="Check if the patient has an infectious / transmissible disease")
    short_comment = fields.Char('Remarks',
                                help="Brief, one-line remark of the disease. Longer description will go on the Extra info field")
    doctor = fields.Many2one('medical.physician', 'Physician', help="Physician who treated or diagnosed the patient")
    diagnosed_date = fields.Date('Date of Diagnosis')
    healed_date = fields.Date('Healed')
    is_active = fields.Boolean('Active disease', default=True)
    age = fields.Integer('Age when diagnosed', help='Patient age at the moment of the diagnosis. Can be estimative')
    pregnancy_warning = fields.Boolean('Pregnancy warning')
    weeks_of_pregnancy = fields.Integer('Contracted in pregnancy week #')
    is_allergy = fields.Boolean('Allergic Disease')
    allergy_type = fields.Selection(
        [('da', 'Drug Allergy'), ('fa', 'Food Allergy'), ('ma', 'Misc Allergy'), ('mc', 'Misc Contraindication'), ],
        'Allergy type', index=True)
    pcs_code = fields.Many2one('medical.procedure', 'Code',
                               help="Procedure code, for example, ICD-10-PCS Code 7-character string")
    treatment_description = fields.Char('Treatment Description')
    date_start_treatment = fields.Date('Start of treatment')
    date_stop_treatment = fields.Date('End of treatment')
    status = fields.Selection(
        [('c', 'chronic'), ('s', 'status quo'), ('h', 'healed'), ('i', 'improving'), ('w', 'worsening'), ],
        'Status of the disease', )
    extra_info = fields.Text('Extra Info')

    _sql_constraints = [
        ('validate_disease_period', "CHECK (diagnosed_date < healed_date )",
         "DIAGNOSED Date must be before HEALED Date !"),
        ('end_treatment_date_before_start', "CHECK (date_start_treatment < date_stop_treatment )",
         "Treatment start Date must be before Treatment end Date !")
    ]


class MedicalDoseUnit(models.Model):
    _name = "medical.dose.unit"
    _description = " Medical Dose Unit"

    name = fields.Char('Unit', required=True, )
    desc = fields.Char('Description')

    _sql_constraints = [
        ('dose_name_uniq', 'unique(name)', 'The Unit must be unique !'),
    ]


class MedicalDrugRoute(models.Model):
    _name = "medical.drug.route"
    _description = "Medical Drug Route"

    name = fields.Char('Route', required=True)
    code = fields.Char('Code')

    _sql_constraints = [
        ('route_name_uniq', 'unique(name)', 'The Name must be unique !'),
    ]


class MedicalDrugForm(models.Model):
    _name = "medical.drug.form"
    _description = "Medical Drug Form"

    name = fields.Char('Form', required=True, )
    code = fields.Char('Code')

    _sql_constraints = [
        ('drug_name_uniq', 'unique(name)', 'The Name must be unique !'),
    ]


class MedicalMedicinePrag(models.Model):
    _name = "medical.medicine.prag"
    _description = "Medical Medicine Prag"

    name = fields.Many2one('product.product', required=True, )
    code = fields.Char('Code')
    price = fields.Float()
    qty_available = fields.Float(related="name.qty_available", string="Quantity Available")

    _sql_constraints = [
        ('drug_name_uniq', 'unique(name)', 'The Name must be unique !'),
    ]

    @api.onchange('name')
    def onchange_name(self):
        if self.name:
            self.price = self.name.lst_price

    # @api.model
    # def create(self,vals):
    #     if 'name' in vals:
    #         if isinstance(vals['name'], str):
    #             product = self.env['product.product'].create({'name':vals['name']})
    #             if product:
    #                 vals.update({'name':product.id})
    #     result = super(MedicalMedicinePrag, self).create(vals)
    #     return result

    @api.model
    def name_create(self, name):
        if name:
            product_id = self.env['product.product'].sudo().create({'name': name})

            medical_medicine_prag_id = self.create({'name': product_id.id})
            return [(medical_medicine_prag_id.id)]


# MEDICATION DOSAGE
class MedicalMedicationDosage(models.Model):
    _name = "medical.medication.dosage"
    _description = "Medicament Common Dosage combinations"

    name = fields.Char('Frequency', help='Common frequency name', required=True, )
    code = fields.Char('Code', help='Dosage Code, such as SNOMED, 229798009 = 3 times per day')
    abbreviation = fields.Char('Abbreviation',
                               help='Dosage abbreviation, such as tid in the US or tds in the UK')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The Unit already exists')]


class MedicalAppointment(models.Model):
    _name = "medical.appointment"
    _description = "Medical Appointment"
    # _rec_name = "complete_name"
    _order = "appointment_sdate desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']


    @api.onchange('services_ids')
    def services_timeadd(self):
        dt = datetime.strptime(str(self.appointment_sdate), '%Y-%m-%d %H:%M:%S')
        server_time = dt + timedelta(hours=5,minutes=30)
        val=[]
        for ids in self.services_ids.ids:
            val.append(ids)
        service_time = self.env['product.product'].search([('id','=',val)])
        main=[]
        for service in service_time:
            main.append(service.duration_id.duration_name)
        minute =sum(main)
        end_time = server_time + timedelta(minutes=minute)
        self.appointment_edate = end_time - timedelta(hours=5,minutes=30)




    @api.onchange('appointment_sdate','doctor')
    def appointment_validation(self):
        validation = self.search([
            ('doctor', '=', self.doctor.id),
            ('appointment_sdate', '>=', self.appointment_sdate),
        ])
        if validation:
            raise ValidationError("Already Booked The Appointment")
        else:
            pass


    def edit_appointment(self, event_id):
        appointment_id = self.search([('id', '=', event_id)], limit=1)
        if appointment_id:
            context = dict(self.env.context)

            tz = pytz.timezone(self.env.user.tz)
            from_time_tz = pytz.utc.localize(appointment_id.appointment_sdate).astimezone(tz)
            from_time = from_time_tz.strftime('%H:%M')
            split_data = from_time.split(':')

            to_time_tz = pytz.utc.localize(appointment_id.appointment_edate).astimezone(tz)
            to_time = to_time_tz.strftime('%H:%M')
            to_split_data = to_time.split(':')

            vals = {
                'appointment_sdate': appointment_id.appointment_sdate,
                'appointment_edate': appointment_id.appointment_edate,
                'appointment_id': appointment_id.id,
                'doctor_id': appointment_id.doctor.id,
                'mobile_number': appointment_id.patient.mobile,
                'patient_id': appointment_id.patient.id,
                'service_ids': [(6, 0, appointment_id.services_ids.ids)],
                'from_time': (float(split_data[0]) * 60 + float(split_data[1])) / 60,
                'to_time': (float(to_split_data[0]) * 60 + float(to_split_data[1])) / 60,
            }
            caw_id = self.env['calender.appointment.wizard'].create(vals)
            return caw_id.id

    def check_appointment(self, event_name):
        record = self.search([('name', '=', event_name)], limit=1)
        app_ids = self.search([
            ('id', '!=', record.id),
            ('doctor', '=', record.doctor.id),
            ('appointment_sdate', '>=', record.appointment_sdate),
            ('appointment_edate', '<=', record.appointment_edate)
        ])
        if app_ids:
            return True
        else:
            return False

    def get_data(self, doctor_id, event_name, index):
        record = self.search([('name', '=', event_name), ('doctor', '=', doctor_id)], limit=1)
        if record:
            return {'index': index, 'patient': record.patient.partner_id.name}
        else:
            return {'index': 0, 'patient': record.patient.partner_id.name}

    @api.model
    def _get_default_doctor(self):
        doc_ids = None
        partner_ids = [x.id for x in
                       self.env['res.partner'].search([('user_id', '=', self.env.user.id), ('is_doctor', '=', True)])]
        if partner_ids:
            doc_ids = [x.id for x in self.env['medical.physician'].search([('name', 'in', partner_ids)])]
        return doc_ids

    def delayed_time(self):
        result = {}
        for patient_data in self:
            if patient_data.checkin_time and patient_data.checkin_time > patient_data.appointment_sdate:
                self.delayed = True
            else:
                self.delayed = False

    @api.onchange('duration_id', 'appointment_sdate')
    def delayed_duration(self):
        if self.duration_id and self.appointment_sdate:
            self.appointment_edate = self.appointment_sdate + timedelta(minutes=self.duration_id.duration_name)

    def _waiting_time(self):
        def compute_time(checkin_time, ready_time):
            now = datetime.now()
            if checkin_time and ready_time:
                ready_time = datetime.strptime(str(ready_time), '%Y-%m-%d %H:%M:%S')
                checkin_time = datetime.strptime(str(checkin_time), '%Y-%m-%d %H:%M:%S')
                delta = relativedelta(ready_time, checkin_time)
                years_months_days = str(delta.hours) + "h " + str(delta.minutes) + "m "
            else:
                years_months_days = "No Waiting time !"

            return years_months_days

        for patient_data in self:
            patient_data.waiting_time = compute_time(patient_data.checkin_time, patient_data.ready_time)

    active = fields.Boolean(default="True")
    allday = fields.Boolean('All Day', default=False)
    operations = fields.One2many('medical.teeth.treatment', 'appt_id', 'Operations')
    doctor = fields.Many2one('medical.physician', 'Doctor', help="Dentist's Name", required=True,
                             default=_get_default_doctor)
    name = fields.Char('Appointment ID', readonly=True, default=lambda self: _('New'))
    patient = fields.Many2one('medical.patient', 'Patient', help="Patient Name", required=True, )
    appointment_sdate = fields.Datetime('Appointment Start', required=True, default=fields.Datetime.now)
    appointment_edate = fields.Datetime('Appointment End', required=True, )
    room_id = fields.Many2one('medical.hospital.oprating.room', 'Room', required=False, )
    urgency = fields.Boolean('Urgent', default=False)
    comments = fields.Text('Note', tracking=1)
    checkin_time = fields.Datetime('Checkin Time', readonly=True, )
    ready_time = fields.Datetime('In Chair', readonly=True, )
    waiting_time = fields.Char('Waiting Time', compute='_waiting_time')
    no_invoice = fields.Boolean('Invoice exempt')
    invoice_done = fields.Boolean('Invoice Done')
    user_id = fields.Many2one('res.users', related='doctor.user_id', string='doctor', store=True)
    inv_id = fields.Many2one('account.move', 'Invoice', readonly=True)
    state = fields.Selection(
        [('draft', 'Unconfirmed'), ('sms_send', 'Sms Send'), ('confirmed', 'Confirmed'), ('missed', 'Missed'),
         ('checkin', 'Checked In'), ('ready', 'In Chair'), ('done', 'Completed'), ('cancel', 'Canceled')], 'State',
        readonly=True, default='draft')
    apt_id = fields.Boolean(default=False)
    apt_process_ids = fields.Many2many('medical.procedure', 'apt_process_rel', 'appointment_id', 'process_id',
                                       "Initial Treatment")
    pres_id1 = fields.One2many('medical.prescription.order', 'pid1', 'Prescription')
    patient_state = fields.Selection([('walkin', 'Walk In'), ('withapt', 'Come with Appointment')], 'Patients status',
                                     required=True, default='withapt')
    #     treatment_ids = fields.One2many ('medical.lab', 'apt_id', 'Treatments')
    saleperson_id = fields.Many2one('res.users', 'Created By', default=lambda self: self.env.user)
    delayed = fields.Boolean(compute='delayed_time', string='Delayed', store=True)
    # service_id = fields.Many2one('product.product', 'Consultation Service')
    services_ids = fields.Many2many('product.product', 'apt_service_rel', 'appointment_id', 'service', 'Services')
    civil_id = fields.Char('Civil Id', related="patient.civil_id")
    mobile = fields.Char('Mobile', related="patient.mobile")
    duration_id = fields.Many2one('duration.duration', 'Duration')
    payment_due = fields.Float(compute='_compute_payment_due', string='Payment Due')
    invoice_amount = fields.Float(compute='_compute_invoice_amount', string='Invoice Amount')
    invoice_amount_char = fields.Char(compute='_compute_invoice_amount', string='Invoice Amount')
    invoice_paid = fields.Float(compute='_compute_invoice_paid', string='Paid Amount')
    invoice_paid_char = fields.Char(compute='_compute_invoice_paid', string='Paid Amount')
    invoice_balance = fields.Float(compute='_compute_invoice_balance', string='Balance')
    invoice_balance_char = fields.Char(compute='_compute_invoice_balance', string='Balance')
    invoice_id = fields.Many2one('account.move')
    note_ids = fields.One2many('medical.notes.history', 'appointment_id', 'Notes History')
    marker_ids = fields.One2many('medical.markers.history', 'appointment_id', 'Face Markers History')
    body_marker_ids = fields.One2many('medical.body.markers.history', 'appointment_id', 'Body Markers History')
    face_order_line_ids = fields.One2many('face.order.line', 'appointment_id', 'Face Lines')
    body_order_line_ids = fields.One2many('body.order.line', 'appointment_id', 'Body Lines')
    treatment_note = fields.Text('Treatment Note Face', tracking=1)
    treatment_body_note = fields.Text('Treatment Note Body', tracking=1)
    complete_name = fields.Char(compute='_name_get_fnc', string="Name")

    face_material_usage_ids = fields.Many2many('product.product', 'apt_face_material_rel', 'appointment_id',
                                               'material_face_usage_id', 'Face Material usage',
                                               domain=[('is_material', '=', True)])
    body_material_usage_ids = fields.Many2many('product.product', 'apt_body_material_rel', 'appointment_id',
                                               'material_body_usage_id', 'Body Material usage',
                                               domain=[('is_material', '=', True)])

    invoice_state = fields.Selection(string="Invoice Status",
                                     selection=[('invoiced', 'Invoiced'), ('payment_registered', 'Payment Registered')])
    is_invoice_state = fields.Boolean(default=False)
    is_register_payment = fields.Boolean(default=False)

    @api.model
    def _name_get_fnc(self):
        for rec in self:
            if rec.patient:
                complete_name = rec.patient.partner_id.name
                if rec.appointment_sdate and rec.appointment_edate:
                    appointment_sdate = rec.appointment_sdate + timedelta(hours=5, minutes=30)
                    appointment_edate = rec.appointment_edate + timedelta(hours=5, minutes=30)
                    complete_name = complete_name + ' ' + str(appointment_sdate.time())[0:5] + ' to ' + str(
                        appointment_edate.time())[0:5]
                rec.complete_name = complete_name
            else:
                rec.complete_name = rec.name

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MedicalAppointment, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                              submenu=submenu)
        return super(MedicalAppointment, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                               submenu=submenu)

    def _compute_invoice_amount(self):
        for rec in self:
            ml_ids = self.env['account.move'].search(
                [('appointment_id', '=', rec.id), ('move_type', '=', 'out_invoice')])
            rec.invoice_amount = sum(ml_ids.mapped('amount_total'))
            rec.invoice_amount_char = "%.2f" % sum(ml_ids.mapped('amount_total'))

    def _compute_invoice_balance(self):
        for rec in self:
            ml_ids = self.env['account.move'].search(
                [('appointment_id', '=', rec.id), ('move_type', '=', 'out_invoice')])
            rec.invoice_balance = sum(ml_ids.mapped('amount_residual'))
            rec.invoice_balance_char = "%.2f" % sum(ml_ids.mapped('amount_residual'))

    @api.depends('invoice_amount', 'invoice_balance')
    def _compute_invoice_paid(self):
        for rec in self:
            rec.invoice_paid = rec.invoice_amount - rec.invoice_balance
            rec.invoice_paid_char = "%.2f" % (rec.invoice_amount - rec.invoice_balance)

    def _compute_payment_due(self):
        for rec in self:
            ml_ids = self.env['account.move'].search([
                ('partner_id', '=', rec.patient.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('amount_residual', '>', 0)])
            rec.payment_due = sum(ml_ids.mapped('amount_residual'))

    _sql_constraints = [
        ('date_check', "CHECK (appointment_sdate <= appointment_edate)",
         "Appointment Start Date must be before Appointment End Date !"), ]

    def get_date(self, date1, lang):
        new_date = ''
        if date1:
            search_id = self.env['res.lang'].search([('code', '=', lang)])
            new_date = datetime.strftime(datetime.strptime(date1, '%Y-%m-%d %H:%M:%S').date(), search_id.date_format)
        return new_date

    def done(self):
        return self.write({'state': 'done'})

    def cancel(self):
        return self.write({'state': 'cancel'})

    def confirm_appointment(self):
        return self.write({'state': 'confirmed'})

    def send_state(self):
        return self.write({'state': 'sms_send'})

    def confirm(self):
        for rec in self:
            appt_end_date = rec.appointment_edate
            attandee_ids = []
            attandee_ids.append(rec.patient.partner_id.id)
            attandee_ids.append(rec.doctor.res_partner_medical_physician_id.id)
            attandee_ids.append(3)
            if not rec.appointment_edate:
                appt_end_date = rec.appointment_sdate
            self.env['calendar.event'].create(
                {'name': rec.name, 'partner_ids': [[6, 0, attandee_ids]], 'start': rec.appointment_sdate,
                 'stop': appt_end_date, })
        self.write({'state': 'confirmed'})

    def sms_send(self):
        return self.write({'state': 'sms_send'})

    def ready(self):
        ready_time = time.strftime('%Y-%m-%d %H:%M:%S')
        self.write({'state': 'ready', 'ready_time': ready_time})
        return True

    def missed(self):
        self.write({'state': 'missed'})

    def checkin(self):
        checkin_time = time.strftime('%Y-%m-%d %H:%M:%S')
        self.write({'state': 'checkin', 'checkin_time': checkin_time})

    def _prepare_invoice(self):
        invoice_vals = {
            'move_type': 'out_invoice',
            'narration': self.comments,
            'invoice_user_id': self.saleperson_id and self.saleperson_id.id,
            'partner_id': self.patient.partner_id.id,
            'invoice_line_ids': [],
            'dentist': self.doctor.id,
            'invoice_date': datetime.today()
        }
        return invoice_vals

    def create_invoices(self):
        invoice_vals = self._prepare_invoice()
        for line in self.operations:
            res = {}
            res.update({
                #                 'name': line.description.name,
                'product_id': line.description.id,
                'price_unit': line.amount,
                'quantity': 1.0,
            })
            invoice_vals['invoice_line_ids'].append((0, 0, res))
        if self.services_ids:
            res = {}
            res.update({
                'name': self.services_ids.name,
                'product_id': self.services_ids.id,
                'price_unit': self.services_ids.lst_price,
                'quantity': 1.0,
            })
            invoice_vals['invoice_line_ids'].append((0, 0, res))
        inv_id = self.env['account.move'].create(invoice_vals)
        if inv_id:
            self.inv_id = inv_id.id
            self.invoice_done = True
        return inv_id

    @api.model
    def create(self, vals):

        for appointmnet in self:
            if appointmnet.room_id.id == vals['room_id']:
                history_start_date = datetime.strptime(str(appointmnet.appointment_sdate), '%Y-%m-%d %H:%M:%S')
                history_end_date = False
                reservation_end_date = False
                if appointmnet.appointment_edate:
                    history_end_date = datetime.strptime(str(appointmnet.appointment_edate), '%Y-%m-%d %H:%M:%S')
                reservation_start_date = datetime.strptime(str(vals['appointment_sdate']), '%Y-%m-%d %H:%M:%S')
                #                 if vals.has_key('appointment_edate') and vals['appointment_edate']:
                if 'appointment_edate' in vals and vals['appointment_edate']:
                    reservation_end_date = datetime.strptime(str(vals['appointment_edate']), '%Y-%m-%d %H:%M:%S')
                if history_end_date and reservation_end_date:
                    if (history_start_date <= reservation_start_date < history_end_date) or (
                            history_start_date < reservation_end_date <= history_end_date) or (
                            (reservation_start_date < history_start_date) and (
                            reservation_end_date >= history_end_date)):
                        raise ValidationError(
                            _('Room  %s is booked in this reservation period!') % (appointmnet.room_id.name))
                elif history_end_date:
                    if (history_start_date <= reservation_start_date) or (
                            history_start_date < reservation_end_date) or (reservation_start_date < history_start_date):
                        raise ValidationError(
                            _('Room  %s is booked in this reservation period!') % (appointmnet.room_id.name))
                elif reservation_end_date:
                    if (history_start_date <= reservation_start_date < history_end_date) or (
                            history_start_date <= history_end_date) or (reservation_start_date < history_start_date):
                        raise ValidationError(
                            _('Room  %s is booked in this reservation period!') % (appointmnet.room_id.name))
            if appointmnet.doctor.id == vals['doctor']:
                reservation_end_date = False
                history_end_date = False
                history_start_date = datetime.strptime(str(appointmnet.appointment_sdate), '%Y-%m-%d %H:%M:%S')
                if appointmnet.appointment_edate:
                    history_end_date = datetime.strptime(str(appointmnet.appointment_edate), '%Y-%m-%d %H:%M:%S')
                reservation_start_date = datetime.strptime(str(vals['appointment_sdate']), '%Y-%m-%d %H:%M:%S')
                if vals['appointment_edate']:
                    reservation_end_date = datetime.strptime(str(vals['appointment_edate']), '%Y-%m-%d %H:%M:%S')
                if (reservation_end_date and history_end_date) and (
                        (history_start_date <= reservation_start_date < history_end_date) or (
                        history_start_date < reservation_end_date <= history_end_date) or (
                                (reservation_start_date < history_start_date) and (
                                reservation_end_date >= history_end_date))):
                    raise ValidationError(
                        _('Doctor  %s is booked in this reservation period !') % (appointmnet.doctor.name.name))

        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('medical.appointment') or 'New'

        result = super(MedicalAppointment, self).create(vals)
        if result.patient and result.pres_id1:
            for prescription in result.pres_id1:
                if result.patient.id != prescription.name.id:
                    raise ValidationError(
                        "You cannot fill in the data of another patient in the prescription.\nThe prescription should have details of the patient defined in 'Patient' Field.")

        self._cr.execute('insert into pat_apt_rel(patient,apid) values (%s,%s)', (vals['patient'], result.id))
        return result


# MEDICATION MARKS HISTORY
class MedicalMarkerHistory(models.Model):
    _name = "medical.markers.history"

    name = fields.Text('Markers Coordinate')
    appointment_id = fields.Many2one('medical.appointment')


# MEDICATION BODY MARKS HISTORY
class MedicalBodyMarkerHistory(models.Model):
    _name = "medical.body.markers.history"

    name = fields.Text('Markers Coordinate')
    appointment_id = fields.Many2one('medical.appointment')


# FACE ORDER LINE
class FaceOrderLine(models.Model):
    _name = "face.order.line"
    _order = "id desc"

    appointment_id = fields.Many2one('medical.appointment')
    product_id = fields.Many2one('product.product', string="Material", domain=[('is_material', '=', True)])
    quantity = fields.Float(string="Quantity", default=1)
    unit_price = fields.Float(string="Unit Price")
    subtotal = fields.Float(string="Subtotal", compute='_compute_subtotal')

    @api.onchange('product_id')
    def onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.unit_price = rec.product_id.lst_price

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.unit_price * rec.quantity


# BODY ORDER LINE
class BodyOrderLine(models.Model):
    _name = "body.order.line"
    _order = "id desc"

    appointment_id = fields.Many2one('medical.appointment')
    product_id = fields.Many2one('product.product', string="Material", domain=[('is_material', '=', True)])
    quantity = fields.Float(string="Quantity", default=1)
    unit_price = fields.Float(string="Unit Price")
    subtotal = fields.Float(string="Subtotal", compute='_compute_subtotal')

    @api.onchange('product_id')
    def onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.unit_price = rec.product_id.lst_price

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.unit_price * rec.quantity


# MEDICATION NOTES HISTORY
class MedicalNotesHistory(models.Model):
    _name = "medical.notes.history"

    appointment_id = fields.Many2one('medical.appointment')
    user_id = fields.Many2one('res.users')
    last_notes = fields.Text('Previous Notes')
    update_notes = fields.Text('Updated Notes')


# PATIENT MEDICATION TREATMENT
class MedicalPatientMedication(models.Model):
    _name = "medical.patient.medication"
    _inherits = {'medical.medication.template': 'template'}
    _description = "Patient Medication"

    template = fields.Many2one('medical.medication.template', 'Template ID', required=True, index=True,
                               ondelete="cascade")
    name = fields.Many2one('medical.patient', 'Patient ID', readonly=True)
    doctor = fields.Many2one('medical.physician', 'Physician', help="Physician who prescribed the medicament")
    is_active = fields.Boolean('Active', default=True,
                               help="Check this option if the patient is currently taking the medication")
    discontinued = fields.Boolean('Discontinued')
    course_completed = fields.Boolean('Course Completed')
    discontinued_reason = fields.Char('Reason for discontinuation',
                                      help="Short description for discontinuing the treatment")
    adverse_reaction = fields.Text('Adverse Reactions',
                                   help="Specific side effects or adverse reactions that the patient experienced")
    notes = fields.Text('Extra Info')
    patient_id = fields.Many2one('medical.patient', 'Patient')

    @api.onchange('course_completed', 'discontinued', 'is_active')
    def onchange_medication(self):
        family_code_id = ""
        if self.course_completed:
            self.is_active = False
            self.discontinued = False
        elif self.is_active == False and self.discontinued == False and self.course_completed == False:
            self.is_active = True
        if self.discontinued:
            self.is_active = False
            self.course_completed = False
        elif self.is_active == False and self.discontinued == False and self.course_completed == False:
            self.is_active = True
        if self.is_active == True:
            self.course_completed = False
            self.discontinued = False
        elif self.is_active == False and self.discontinued == False and self.course_completed == False:
            self.course_completed = True


# PRESCRIPTION ORDER
class MedicalPrescriptionOrder(models.Model):
    _name = "medical.prescription.order"
    _description = "prescription order" 

    @api.model
    def _get_default_doctor(self):
        doc_ids = None
        partner_ids = self.env['res.partner'].search([('user_id', '=', self.env.user.id), ('is_doctor', '=', True)])
        if partner_ids:
            partner_ids = [x.id for x in partner_ids]
            doc_ids = [x.id for x in self.env['medical.physician'].search([('name', 'in', partner_ids)])]
        return doc_ids

    name = fields.Many2one('medical.patient', string="Patient ID", required=True)
    prescription_id = fields.Char('Prescription ID',
                                  help='Type in the ID of this prescription')
    prescription_date = fields.Datetime('Prescription Date', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', 'Log In User', readonly=True, default=lambda self: self.env.user)
    pharmacy = fields.Many2one('res.partner', 'Pharmacy', domain=[('is_pharmacy', '=', True)])
    prescription_line = fields.One2many('medical.prescription.line', 'name', 'Prescription line')
    notes = fields.Text('Prescription Notes')
    pid1 = fields.Many2one('medical.appointment', 'Appointment', )
    doctor = fields.Many2one('medical.physician', 'Prescribing Doctor', help="Physician's Name",
                             default=_get_default_doctor)
    p_name = fields.Char('Demo', default=False)
    no_invoice = fields.Boolean('Invoice exempt')
    invoice_done = fields.Boolean('Invoice Done')
    state = fields.Selection([('tobe', 'To be Invoiced'), ('invoiced', 'Invoiced'), ('cancel', 'Cancel')],
                             'Invoice Status', default='tobe')
    inv_id = fields.Many2one('account.move', 'Invoice', readonly=True)
    pricelist_id = fields.Many2one('product.pricelist', 'Pricelist', required=True)

    _sql_constraints = [
        ('pid1', 'unique (pid1)', 'Prescription must be unique per Appointment'),
        ('prescription_id', 'unique (prescription_id)', 'Prescription ID must be unique')]

    @api.onchange('name')
    def onchange_name(self):
        domain_list = []
        domain = {}
        if self.name:
            apt_ids = self.search([('name', '=', self.name.id)])
            for apt in apt_ids:
                if apt.pid1:
                    domain_list.append(apt.pid1.id)
        domain['pid1'] = [('id', 'not in', domain_list)]
        return {'domain': domain}

    @api.model
    def create(self, vals):
        if vals.get('prescription_id', 'New') == 'New':
            vals['prescription_id'] = self.env['ir.sequence'].next_by_code('medical.prescription') or 'New'
        result = super(MedicalPrescriptionOrder, self).create(vals)
        return result

    #         def onchange_p_name(self, cr, uid, ids, p_name,context = None ):
    #          n_name=context.get('name')
    #          d_name=context.get('physician_id')
    #          v={}
    #          v['name'] =  n_name
    #          v['doctor'] =  d_name
    #          return {'value': v}

    def get_date(self, date1, lang):
        new_date = ''
        if date1:
            search_id = self.env['res.lang'].search([('code', '=', lang)])
            new_date = datetime.strftime(datetime.strptime(date1, '%Y-%m-%d %H:%M:%S').date(), search_id.date_format)
        return new_date

    def _prepare_invoice(self):
        invoice_vals = {
            'move_type': 'out_invoice',
            'narration': self.notes,
            'invoice_user_id': self.user_id and self.user_id.id,
            'partner_id': self.name.partner_id.id,
            'invoice_line_ids': [],
            'dentist': self.doctor.id,
            'invoice_date': datetime.today()
        }
        return invoice_vals

    def create_invoices(self):
        if not self.prescription_line:
            raise UserError(_("Please add medicine line."))
        invoice_vals = self._prepare_invoice()
        for line in self.prescription_line:
            res = {}
            res.update({
                #                 'name': line.medicine_id.name.name,
                'product_id': line.medicine_id.name.id,
                'price_unit': line.medicine_id.price,
                'quantity': line.quantity,
            })
            invoice_vals['invoice_line_ids'].append((0, 0, res))
        inv_id = self.env['account.move'].create(invoice_vals)
        if inv_id:
            self.inv_id = inv_id.id
            self.state = 'invoiced'
        return inv_id

    
    @api.onchange('pid1')
    def get_appoinment_details(self):
        if self.pid1:
            self.doctor = self.pid1.doctor
            self.name = self.pid1.patient

    


# PRESCRIPTION LINE

class MedicalPrescriptionLine(models.Model):
    _name = "medical.prescription.line"
    _description = "Basic prescription object"

    medicine_id = fields.Many2one('medical.medicine.prag', 'Medicine', required=True, ondelete="cascade")
    name = fields.Many2one('medical.prescription.order', 'Prescription ID')
    quantity = fields.Integer('Quantity', default=1)
    note = fields.Char('Note', help='Short comment on the specific drug')
    dose = fields.Float('Dose', help="Amount of medication (eg, 250 mg ) each time the patient takes it")
    dose_unit = fields.Many2one('medical.dose.unit', 'Dose Unit', help="Unit of measure for the medication to be taken")
    form = fields.Many2one('medical.drug.form', 'Form', help="Drug form, such as tablet or gel")
    qty = fields.Integer('x', default=1, help="Quantity of units (eg, 2 capsules) of the medicament")
    common_dosage = fields.Many2one('medical.medication.dosage', 'Frequency',
                                    help="Common / standard dosage frequency for this medicament")
    duration = fields.Integer('Duration',
                              help="Time in between doses the patient must wait (ie, for 1 pill each 8 hours, put here 8 and select 'hours' in the unit field")
    duration_period = fields.Selection([
        ('seconds', 'seconds'),
        ('minutes', 'minutes'),
        ('hours', 'hours'),
        ('days', 'days'),
        ('weeks', 'weeks'),
        ('wr', 'when required'),
    ], 'Duration Unit', default='days', )


# HEALTH CENTER / HOSPITAL INFRASTRUCTURE
class MedicalHospitalBuilding(models.Model):
    _name = "medical.hospital.building"
    _description = "Medical hospital Building"

    name = fields.Char('Name', required=True, help="Name of the building within the institution")
    institution = fields.Many2one('res.partner', 'Institution', domain=[('is_institution', '=', "1")],
                                  help="Medical Center")
    code = fields.Char('Code')
    extra_info = fields.Text('Extra Info')


class MedicalHospitalUnit(models.Model):
    _name = "medical.hospital.unit"
    _description = "Medical Hospital Unit"
    name = fields.Char('Name', required=True, help="Name of the unit, eg Neonatal, Intensive Care, ...")
    institution = fields.Many2one('res.partner', 'Institution', domain=[('is_institution', '=', "1")],
                                  help="Medical Center")
    code = fields.Char('Code')
    extra_info = fields.Text('Extra Info')


class MedicalHospitalOpratingRoom(models.Model):
    _name = "medical.hospital.oprating.room"
    _description = "Medical Hospital Oprating room"

    name = fields.Char('Name', required=True, help='Name of the Operating Room')
    institution = fields.Many2one('res.partner', 'Institution', domain=[('is_institution', '=', True)],
                                  help='Medical Center')
    building = fields.Many2one('medical.hospital.building', 'Building', index=True)
    unit = fields.Many2one('medical.hospital.unit', 'Unit')
    extra_info = fields.Text('Extra Info')

    _sql_constraints = [
        ('name_uniq', 'unique (name, institution)', 'The Operating Room code must be unique per Health Center.')]


class MedicalProcedure(models.Model):
    _description = "Medical Procedure"
    _name = "medical.procedure"

    name = fields.Char('Code', required=True)
    description = fields.Char('Long Text')

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(['|', ('name', operator, name), ('description', operator, name)])
        if not recs:
            recs = self.search([('name', operator, name)])
        return recs.name_get()


class TeethCode(models.Model):
    _description = "teeth code"
    _name = "teeth.code"

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    palmer_name = fields.Char('palmer_name', required=True)
    palmer_internal_id = fields.Integer('Palmar Internam ID')
    iso = fields.Char('iso', required=True)
    internal_id = fields.Integer('Internal IDS')

    def write(self, vals):
        for rec in self:
            #             if vals.has_key('palmer_name'):
            if 'palmer_name' in vals:
                lst = self.search([('palmer_internal_id', '=', rec.palmer_internal_id)])
                #                 lst.write({'palmer_name': vals['palmer_name']})
                super(TeethCode, lst).write({'palmer_name': vals['palmer_name']})
        return super(TeethCode, self).write(vals)

    @api.model
    def name_get(self):
        res = []
        teeth_obj = self.env['chart.selection'].search([])
        obj = teeth_obj[-1]
        for each in self:
            name = each.name
            if obj.type == 'palmer':
                name = str(each.palmer_internal_id)
                if each.internal_id <= 8:
                    name += '-1x'
                elif each.internal_id <= 16:
                    name += '-2x'
                elif each.internal_id <= 24:
                    name += '-3x'
                else:
                    name += '-4x'
            elif obj.type == 'iso':
                name = each.iso
            res.append((each.id, name))
        return res

    def get_teeth_code(self):
        l1 = [];
        d1 = {};
        teeth_ids = self.env['teeth.code'].search([])
        teeth_obj = self.env['chart.selection'].search([])
        teeth_type = teeth_obj[-1]
        for teeth in teeth_ids:
            if teeth_type.type == 'palmer':
                d1[int(teeth.internal_id)] = teeth.palmer_name
            elif teeth_type.type == 'iso':
                d1[int(teeth.internal_id)] = teeth.iso
            else:
                d1[int(teeth.internal_id)] = teeth.name
        x = d1.keys()
        x = sorted(x)
        for i in x:
            l1.append(d1[i])
        return l1;


class ChartSelection(models.Model):
    _description = "teeth chart selection"
    _name = "chart.selection"

    type = fields.Selection(
        [('universal', 'Universal Numbering System'), ('palmer', 'Palmer Method'), ('iso', 'ISO FDI Numbering System')],
        'Select Chart Type', default='universal')


class ProductCategory(models.Model):
    _inherit = "product.category"
    _description = "Product Category"

    treatment = fields.Boolean('Treatment')

    def get_treatment_categs(self):
        all_records = self.search([])
        treatment_list = []
        for each_rec in all_records:
            if each_rec.treatment == True:
                treatment_list.append({'treatment_categ_id': each_rec.id, 'name': each_rec.name, 'treatments': []})

        product_rec = self.env['product.product'].search([('is_treatment', '=', True)])
        for each_product in product_rec:
            each_template = each_product.product_tmpl_id
            for each_treatment in treatment_list:
                if each_template.categ_id.id == each_treatment['treatment_categ_id']:
                    each_treatment['treatments'].append(
                        {'treatment_id': each_product.id, 'treatment_name': each_template.name,
                         'action': each_product.action_perform})
                    break

        return treatment_list


class MedicalTeethTreatment(models.Model):
    _description = "Medical Teeth Treatment"
    _name = "medical.teeth.treatment"

    #     def name_search(self, name, args=None, operator='ilike', limit=100):
    #         x = super(medical_teeth_treatment, self).name_search(self)
    #         return x
    #
    #     def name_get(self):
    #         x = super(medical_teeth_treatment, self).name_get()
    #         return x
    #
    #     def _get_tooth_name(self, cr, uid, ids, name, args, context):
    #         res = {}
    #         self_obj = self.browse(cr, uid, ids, context)
    #         for obj in self_obj:
    #             tooth = self.pool.get('ir.model.data').get_object(cr, uid, 'pragtech_dental_management', 'teeth_chart_first_record')
    #             if tooth:
    #                 if tooth.type == 'iso':
    #                     res[obj.id] = obj.teeth_id.iso
    #                 elif tooth.type == 'palmer':
    #                     res[obj.id] = obj.teeth_id.palmer_name
    #                 else:
    #                     res[obj.id] = obj.teeth_id.name
    #         return res

    patient_id = fields.Many2one('medical.patient', 'Patient Details')
    teeth_id = fields.Many2one('teeth.code', 'Tooth')
    description = fields.Many2one('product.product', 'Description', domain=[('is_treatment', '=', True)])
    detail_description = fields.Text('Surface')
    state = fields.Selection(
        [('planned', 'Planned'), ('condition', 'Condition'), ('completed', 'Completed'), ('in_progress', 'In Progress'),
         ('invoiced', 'Invoiced')], 'Status', default='planned')
    dentist = fields.Many2one('medical.physician', 'Dentist')
    amount = fields.Float('Amount')
    appt_id = fields.Many2one('medical.appointment', 'Appointment ID')
    teeth_code_rel = fields.Many2many('teeth.code', 'teeth_code_medical_teeth_treatment_rel', 'operation', 'teeth')


class PatientBirthdayAlert(models.Model):
    _name = "patient.birthday.alert"
    _description = "Patient Birthday Alert"

    patient_id = fields.Many2one('medical.patient', 'Patient ID', readonly=True)
    dob = fields.Date('DOB', readonly=True)
    date_create = fields.Datetime('Create Date', readonly=True)


class pland_visit_alert(models.Model):
    _name = "planned.visit.alert"
    _description = "Planned Visit Alert"

    patient_name = fields.Many2one('medical.patient', 'Patient Name', readonly=True)
    treatment_name = fields.Many2one('product.product', 'Treatment Name', readonly=True)
    operated_date = fields.Datetime('Last Operated Date', readonly=True)


class patient_complaint(models.Model):
    _name = "patient.complaint"
    _description = "Patient Complaint"

    patient_id = fields.Many2one('medical.patient', 'Patient ID', required=True)
    complaint_subject = fields.Char('Complaint Subject', required=True)
    complaint_date = fields.Datetime('Complaint Date')
    complaint = fields.Text('Complaint')
    action_ta = fields.Text('Action Taken Against')


class ir_attachment(models.Model):
    """
    Form for Attachment details
    """
    _inherit = "ir.attachment"
    # _name = "ir.attachment"

    patient_id = fields.Many2one('medical.patient', 'Patient')
