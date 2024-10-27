"""empty message

Revision ID: 1596f2fcc7af
Revises: 58cb4f88af8f
Create Date: 2024-10-23 22:11:13.921899

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1596f2fcc7af'
down_revision = '58cb4f88af8f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('auth_id',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('auth_id',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)

    # ### end Alembic commands ###
